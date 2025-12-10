"""Documentation fetcher for version-correct package docs."""

import asyncio
import hashlib
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from theauditor.utils.rate_limiter import (
    RATE_LIMIT_BACKOFF,
    TIMEOUT_CRAWL,
    TIMEOUT_FETCH,
    TIMEOUT_PROBE,
    get_rate_limiter,
)

from . import get_manager

try:
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md

    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


DEFAULT_ALLOWLIST = [
    "https://registry.npmjs.org/",
    "https://pypi.org/",
    "https://raw.githubusercontent.com/",
    "https://readthedocs.io/",
    "https://readthedocs.org/",
    "https://docs.python.org/",
    "https://flask.palletsprojects.com/",
    "https://docs.sqlalchemy.org/",
    "https://numpy.org/doc/",
    "https://pandas.pydata.org/",
    "https://scikit-learn.org/",
    "https://pytorch.org/docs/",
    "https://www.tensorflow.org/",
    "https://fastapi.tiangolo.com/",
    "https://django.readthedocs.io/",
    "https://www.django-rest-framework.org/",
    "https://crates.io/",
    "https://docs.rs/",
    "https://pkg.go.dev/",
    "https://proxy.golang.org/",
]


def _validate_package_name(name: str, manager: str) -> bool:
    """Validate package name format for a package manager."""
    if not name or len(name) > 214:
        return False
    if manager == "npm":
        return bool(re.match(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", name))
    elif manager == "py":
        return bool(re.match(r"^[a-zA-Z0-9][\w.-]*$", name))
    elif manager == "docker":
        return bool(re.match(r"^[a-z0-9][\w./:-]*$", name))
    return False


def fetch_docs(
    deps: list[dict[str, Any]],
    allow_net: bool = True,
    allowlist: list[str] | None = None,
    offline: bool = False,
    output_dir: str = "./.pf/context/docs",
) -> dict[str, Any]:
    """Fetch version-correct documentation for dependencies."""
    if offline or not allow_net:
        return {
            "mode": "offline",
            "fetched": 0,
            "cached": 0,
            "skipped": len(deps),
            "errors": [],
        }

    if not HTTPX_AVAILABLE:
        return {
            "mode": "error",
            "error": "httpx not installed. Run: pip install httpx",
            "fetched": 0,
            "cached": 0,
            "skipped": len(deps),
            "errors": ["httpx not installed"],
        }

    if allowlist is None:
        allowlist = DEFAULT_ALLOWLIST

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    return asyncio.run(_fetch_docs_async(deps, output_path, allowlist))


async def _fetch_docs_async(
    deps: list[dict[str, Any]],
    output_path: Path,
    allowlist: list[str],
) -> dict[str, Any]:
    """Async documentation fetcher."""
    stats = {
        "mode": "online",
        "fetched": 0,
        "cached": 0,
        "skipped": 0,
        "errors": [],
    }

    needs_fetch = []
    for dep in deps:
        if _is_cached(dep, output_path):
            stats["cached"] += 1
        else:
            needs_fetch.append(dep)

    if not needs_fetch:
        return stats

    semaphore = asyncio.Semaphore(20)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(TIMEOUT_FETCH, connect=5.0),
        follow_redirects=True,
        headers={"User-Agent": "TheAuditor/1.0 (docs fetcher)"},
    ) as client:
        tasks = [
            _fetch_one_doc(client, dep, output_path, allowlist, semaphore) for dep in needs_fetch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for dep, result in zip(needs_fetch, results, strict=True):
            if isinstance(result, Exception):
                stats["errors"].append(f"{dep['name']}: {type(result).__name__}")
                stats["skipped"] += 1
            elif result == "fetched":
                stats["fetched"] += 1
            elif result == "cached":
                stats["cached"] += 1
            else:
                stats["skipped"] += 1

    return stats


async def _fetch_one_doc(
    client: httpx.AsyncClient,
    dep: dict[str, Any],
    output_path: Path,
    allowlist: list[str],
    semaphore: asyncio.Semaphore,
) -> str:
    """Fetch documentation for a single dependency."""
    manager = dep.get("manager", "")
    limiter = get_rate_limiter("docs")

    async with semaphore:
        await limiter.acquire()

        try:
            if manager == "npm":
                return await _fetch_npm_docs_async(client, dep, output_path, allowlist)
            elif manager == "py":
                return await _fetch_pypi_docs_async(client, dep, output_path, allowlist)
            elif manager in ("cargo", "go"):
                mgr = get_manager(manager)
                if mgr:
                    return await mgr.fetch_docs_async(client, dep, output_path, allowlist)
                return "skipped"
            else:
                return "skipped"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                await asyncio.sleep(RATE_LIMIT_BACKOFF)
                return "rate_limited"
            return "error"
        except Exception:
            return "error"


def _is_cached(dep: dict[str, Any], output_dir: Path) -> bool:
    """Quick cache check without network calls."""
    name = dep.get("name", "")
    version = dep.get("version", "")
    manager = dep.get("manager", "")

    pkg_dir = _get_pkg_dir(output_dir, manager, name, version)
    doc_file = pkg_dir / "doc.md"
    meta_file = pkg_dir / "meta.json"

    if not (doc_file.exists() and meta_file.exists()):
        return False

    try:
        with open(meta_file, encoding="utf-8") as f:
            meta = json.load(f)
        last_checked = datetime.fromisoformat(meta["last_checked"])

        return (datetime.now() - last_checked).days < 7
    except (json.JSONDecodeError, KeyError, ValueError):
        return False


def _get_pkg_dir(output_dir: Path, manager: str, name: str, version: str) -> Path:
    """Get the package-specific cache directory."""

    if version.startswith("git") or "://" in version:
        version_hash = hashlib.md5(version.encode()).hexdigest()[:8]
        safe_version = f"git-{version_hash}"
    else:
        safe_version = re.sub(r"[:/\\]", "_", version)

    if manager == "npm":
        safe_name = name.replace("@", "_at_").replace("/", "_")
    else:
        safe_name = re.sub(r"[/\\]", "_", name)

    return output_dir / manager / f"{safe_name}@{safe_version}"


def _is_url_allowed(url: str, allowlist: list[str]) -> bool:
    """Check if URL is in the allowlist."""
    return any(url.startswith(allowed) for allowed in allowlist)


async def _fetch_npm_docs_async(
    client: httpx.AsyncClient,
    dep: dict[str, Any],
    output_dir: Path,
    allowlist: list[str],
) -> str:
    """Fetch documentation for an npm package."""
    name = dep["name"]
    version = dep["version"]

    if not _validate_package_name(name, "npm"):
        return "skipped"

    pkg_dir = _get_pkg_dir(output_dir, "npm", name, version)
    pkg_dir.mkdir(parents=True, exist_ok=True)
    doc_file = pkg_dir / "doc.md"
    meta_file = pkg_dir / "meta.json"

    safe_name = urllib.parse.quote(name, safe="")
    safe_version = urllib.parse.quote(version, safe="")
    url = f"https://registry.npmjs.org/{safe_name}/{safe_version}"

    if not _is_url_allowed(url, allowlist):
        return "skipped"

    response = await client.get(url, timeout=TIMEOUT_FETCH)
    response.raise_for_status()
    data = response.json()

    readme = data.get("readme", "")
    repository = data.get("repository", {})
    homepage = data.get("homepage", "")

    if len(readme) < 500:
        github_readme = await _fetch_github_readme_async(client, repository, homepage, allowlist)
        if github_readme and len(github_readme) > len(readme):
            readme = github_readme

    if len(readme) < 500:
        readme = _enhance_npm_readme(data, readme)

    with open(doc_file, "w", encoding="utf-8") as f:
        f.write(f"# {name}@{version}\n\n")
        f.write(f"**Package**: [{name}](https://www.npmjs.com/package/{name})\n")
        f.write(f"**Version**: {version}\n")
        if homepage:
            f.write(f"**Homepage**: {homepage}\n")
        f.write("\n---\n\n")
        f.write(readme)
        if "## Usage" not in readme and "## Example" not in readme:
            f.write(f"\n\n## Installation\n\n```bash\nnpm install {name}\n```\n")

    meta = {
        "source_url": url,
        "last_checked": datetime.now().isoformat(),
        "repository": repository,
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return "fetched"


async def _fetch_pypi_docs_async(
    client: httpx.AsyncClient,
    dep: dict[str, Any],
    output_dir: Path,
    allowlist: list[str],
) -> str:
    """Fetch documentation for a PyPI package."""
    name = dep["name"].strip()
    version = dep["version"]

    if not _validate_package_name(name, "py"):
        return "skipped"

    pkg_dir = _get_pkg_dir(output_dir, "py", name, version)
    pkg_dir.mkdir(parents=True, exist_ok=True)
    doc_file = pkg_dir / "doc.md"
    meta_file = pkg_dir / "meta.json"

    safe_name = urllib.parse.quote(name, safe="")
    if version in ["latest", "git"]:
        if version == "git":
            return "skipped"
        url = f"https://pypi.org/pypi/{safe_name}/json"
    else:
        safe_version = urllib.parse.quote(version, safe="")
        url = f"https://pypi.org/pypi/{safe_name}/{safe_version}/json"

    if not _is_url_allowed(url, allowlist):
        return "skipped"

    response = await client.get(url, timeout=TIMEOUT_FETCH)
    response.raise_for_status()
    data = response.json()

    info = data.get("info", {})
    description = info.get("description", "")
    summary = info.get("summary", "")
    project_urls = info.get("project_urls", {}) or {}

    if len(description) < 500:
        github_readme = await _try_github_from_project_urls(client, project_urls, info, allowlist)
        if github_readme and len(github_readme) > len(description):
            description = github_readme

    if len(description) < 1000:
        crawled = await _crawl_docs_smart(client, project_urls, name, version, allowlist)
        if crawled:
            for page_name, content in crawled.items():
                page_file = pkg_dir / f"{page_name}.md"
                with open(page_file, "w", encoding="utf-8") as f:
                    f.write(f"# {name}@{version} - {page_name.title()}\n\n")
                    f.write(content)

    with open(doc_file, "w", encoding="utf-8") as f:
        f.write(f"# {name}@{version}\n\n")
        f.write(f"**Package**: [{name}](https://pypi.org/project/{name}/)\n")
        f.write(f"**Version**: {version}\n")
        if project_urls:
            f.write("\n**Links**:\n")
            for key, proj_url in list(project_urls.items())[:5]:
                if proj_url:
                    f.write(f"- {key}: {proj_url}\n")
        f.write("\n---\n\n")
        if summary and summary not in description:
            f.write(f"**Summary**: {summary}\n\n")
        f.write(description)
        if "pip install" not in description.lower():
            f.write(f"\n\n## Installation\n\n```bash\npip install {name}\n```\n")

    meta = {
        "package": name,
        "version": version,
        "source_url": url,
        "last_checked": datetime.now().isoformat(),
        "project_urls": project_urls,
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return "fetched"


async def _fetch_github_readme_async(
    client: httpx.AsyncClient,
    repository: dict | str,
    homepage: str,
    allowlist: list[str],
) -> str | None:
    """Fetch README from GitHub repository."""

    repo_url = repository.get("url", "") if isinstance(repository, dict) else repository or ""

    urls_to_try = [repo_url, homepage] if homepage else [repo_url]

    for url in urls_to_try:
        if not url or "github.com" not in url.lower():
            continue

        match = re.search(r"github\.com[:/]([^/]+)/([^/\s]+)", url)
        if not match:
            continue

        owner, repo = match.groups()
        repo = repo.replace(".git", "").rstrip("/")
        safe_owner = urllib.parse.quote(owner, safe="")
        safe_repo = urllib.parse.quote(repo, safe="")

        for branch in ["main", "master"]:
            raw_url = (
                f"https://raw.githubusercontent.com/{safe_owner}/{safe_repo}/{branch}/README.md"
            )

            if not _is_url_allowed(raw_url, allowlist):
                continue

            try:
                head_resp = await client.head(raw_url, timeout=TIMEOUT_PROBE)
                if head_resp.status_code != 200:
                    continue

                resp = await client.get(raw_url, timeout=TIMEOUT_CRAWL)
                if resp.status_code == 200:
                    return resp.text
            except Exception:
                continue

    return None


async def _try_github_from_project_urls(
    client: httpx.AsyncClient,
    project_urls: dict,
    info: dict,
    allowlist: list[str],
) -> str | None:
    """Try to find and fetch GitHub README from project URLs."""
    all_urls = list(project_urls.values())
    all_urls.append(info.get("home_page", ""))
    all_urls.append(info.get("download_url", ""))

    for url in all_urls:
        if url and "github.com" in url.lower():
            readme = await _fetch_github_readme_async(client, url, "", allowlist)
            if readme and len(readme) > 500:
                return readme

    return None


async def _crawl_docs_smart(
    client: httpx.AsyncClient,
    project_urls: dict,
    package_name: str,
    version: str,
    allowlist: list[str],
) -> dict[str, str]:
    """Smart documentation crawler with REDUCED URL patterns."""
    results = {}

    doc_url = None
    for key, url in project_urls.items():
        if url and ("readthedocs" in url.lower() or "docs" in key.lower()):
            doc_url = url.rstrip("/")
            break

    if not doc_url:
        return results

    extended_allowlist = allowlist + [
        doc_url,
        f"https://{package_name}.readthedocs.io/",
        f"https://{package_name}.readthedocs.org/",
    ]

    if not await _probe_url(client, doc_url, extended_allowlist):
        return results

    version_parts = version.split(".")
    major_minor = ".".join(version_parts[:2]) if len(version_parts) >= 2 else version

    root_patterns = [
        f"{doc_url}/en/stable/",
        f"{doc_url}/en/latest/",
        f"{doc_url}/en/{major_minor}/",
        doc_url + "/",
    ]

    working_root = None
    for pattern in root_patterns:
        if await _probe_url(client, pattern, extended_allowlist):
            working_root = pattern
            break

    if not working_root:
        working_root = doc_url + "/"

    priority_pages = ["quickstart", "api", "tutorial"]

    limiter = get_rate_limiter("docs")

    for page in priority_pages:
        await limiter.acquire()

        page_url = f"{working_root}{page}/"
        content = await _fetch_and_convert_async(client, page_url, extended_allowlist)

        if content and len(content) > 200:
            results[page] = content

        if page not in results:
            page_url_html = f"{working_root}{page}.html"
            content = await _fetch_and_convert_async(client, page_url_html, extended_allowlist)
            if content and len(content) > 200:
                results[page] = content

    return results


async def _probe_url(
    client: httpx.AsyncClient,
    url: str,
    allowlist: list[str],
) -> bool:
    """Fast HEAD probe to check if URL exists."""
    if not _is_url_allowed(url, allowlist):
        return False

    try:
        resp = await client.head(url, timeout=TIMEOUT_PROBE)
        return resp.status_code == 200
    except Exception:
        return False


async def _fetch_and_convert_async(
    client: httpx.AsyncClient,
    url: str,
    allowlist: list[str],
) -> str | None:
    """Fetch HTML and convert to markdown."""
    if not _is_url_allowed(url, allowlist):
        return None

    try:
        resp = await client.get(url, timeout=TIMEOUT_CRAWL)
        if resp.status_code != 200:
            return None

        html_content = resp.text

        if BEAUTIFULSOUP_AVAILABLE:
            return _convert_html_bs4(html_content)
        else:
            return _convert_html_regex(html_content)

    except Exception:
        return None


def _convert_html_bs4(html_content: str) -> str | None:
    """Convert HTML to markdown using BeautifulSoup."""
    soup = BeautifulSoup(html_content, "html.parser")

    for element in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        element.decompose()

    main_content = None
    for selector in ["article", "main", ".document", ".rst-content", ".content", "#content"]:
        main_content = soup.select_one(selector)
        if main_content:
            break

    if not main_content:
        main_content = soup.find("body")

    if not main_content:
        return None

    markdown = md(
        str(main_content),
        heading_style="ATX",
        bullets="-",
        strip=["a"],
    )

    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip() if len(markdown) > 100 else None


def _convert_html_regex(html_content: str) -> str:
    """Fallback regex-based HTML to markdown conversion."""

    html_content = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL)
    html_content = re.sub(r"<style[^>]*>.*?</style>", "", html_content, flags=re.DOTALL)

    html_content = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", html_content, flags=re.I)
    html_content = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", html_content, flags=re.I)
    html_content = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n", html_content, flags=re.I)
    html_content = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", html_content, flags=re.I)
    html_content = re.sub(
        r"<pre[^>]*>(.*?)</pre>", r"```\n\1\n```", html_content, flags=re.DOTALL | re.I
    )
    html_content = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", html_content, flags=re.I)
    html_content = re.sub(r"<[^>]+>", "", html_content)

    html_content = re.sub(r"\n{3,}", "\n\n", html_content)
    return html_content.strip()


def _enhance_npm_readme(data: dict[str, Any], readme: str) -> str:
    """Enhance minimal npm README with package metadata."""
    enhanced = readme or ""

    description = data.get("description", "")
    if description and description not in enhanced:
        enhanced = f"{description}\n\n{enhanced}"

    keywords = data.get("keywords", [])
    if keywords and "keywords" not in enhanced.lower():
        enhanced += f"\n\n## Keywords\n\n{', '.join(keywords)}"

    main = data.get("main", "")
    if main:
        enhanced += f"\n\n## Entry Point\n\nMain file: `{main}`"

    return enhanced


def check_latest(
    deps: list[dict[str, Any]],
    allow_net: bool = True,
    offline: bool = False,
) -> dict[str, Any]:
    """Check latest versions and compare to locked versions."""
    from .deps import check_latest_versions

    if offline or not allow_net:
        return {"mode": "offline", "checked": 0, "outdated": 0}

    latest_info = check_latest_versions(deps, allow_net=allow_net, offline=offline, root_path=".")

    outdated = sum(1 for info in latest_info.values() if info.get("is_outdated"))

    return {
        "mode": "online",
        "checked": len(latest_info),
        "outdated": outdated,
    }
