"""Documentation fetcher for version-correct package docs."""

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from theauditor.security import sanitize_path, sanitize_url_component, validate_package_name, SecurityError

try:
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False


# Default allowlist for registries and documentation sites
DEFAULT_ALLOWLIST = [
    # Package registries
    "https://registry.npmjs.org/",
    "https://pypi.org/",
    "https://raw.githubusercontent.com/",
    # Documentation hosting platforms
    "https://readthedocs.io/",
    "https://readthedocs.org/",
    "https://docs.python.org/",
    # Common documentation site patterns
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
    # Generic GitHub Pages pattern (will be extended per-package)
]

# Rate limiting configuration - optimized for minimal runtime
RATE_LIMIT_DELAY = 0.15  # Average delay between requests (balanced for npm/PyPI)
RATE_LIMIT_BACKOFF = 15  # Backoff on 429/disconnect (15s gives APIs time to reset)


def fetch_docs(
    deps: List[Dict[str, Any]],
    allow_net: bool = True,
    allowlist: Optional[List[str]] = None,
    offline: bool = False,
    output_dir: str = "./.pf/context/docs"
) -> Dict[str, Any]:
    """
    Fetch version-correct documentation for dependencies.
    
    Args:
        deps: List of dependency objects from deps.py
        allow_net: Whether network access is allowed
        allowlist: List of allowed URL prefixes (uses DEFAULT_ALLOWLIST if None)
        offline: Force offline mode
        output_dir: Base directory for cached docs
    
    Returns:
        Summary of fetch operations
    """
    if offline or not allow_net:
        return {
            "mode": "offline",
            "fetched": 0,
            "cached": 0,
            "skipped": len(deps),
            "errors": []
        }

    if allowlist is None:
        allowlist = DEFAULT_ALLOWLIST

    try:
        output_path = sanitize_path(output_dir, ".")
        output_path.mkdir(parents=True, exist_ok=True)
    except SecurityError as e:
        return {
            "mode": "error",
            "error": f"Invalid output directory: {e}",
            "fetched": 0,
            "cached": 0,
            "skipped": len(deps)
        }

    stats = {
        "mode": "online",
        "fetched": 0,
        "cached": 0,
        "skipped": 0,
        "errors": []
    }

    # FIRST PASS: Check what's cached
    needs_fetch = []
    for dep in deps:
        # Quick cache check without network
        cache_result = _check_cache_for_dep(dep, output_path)
        if cache_result["cached"]:
            stats["cached"] += 1
        else:
            needs_fetch.append(dep)
    
    # Early exit if everything is cached
    if not needs_fetch:
        return stats
    
    # SECOND PASS: Fetch only what we need, with per-service rate limiting
    npm_rate_limited_until = 0
    pypi_rate_limited_until = 0
    
    for i, dep in enumerate(needs_fetch):
        try:
            current_time = time.time()
            
            # Check if this service is rate limited
            if dep["manager"] == "npm" and current_time < npm_rate_limited_until:
                stats["skipped"] += 1
                stats["errors"].append(f"{dep['name']}: Skipped (npm rate limited)")
                continue
            elif dep["manager"] == "py" and current_time < pypi_rate_limited_until:
                stats["skipped"] += 1
                stats["errors"].append(f"{dep['name']}: Skipped (PyPI rate limited)")
                continue
            
            # Fetch the documentation
            if dep["manager"] == "npm":
                result = _fetch_npm_docs(dep, output_path, allowlist)
            elif dep["manager"] == "py":
                result = _fetch_pypi_docs(dep, output_path, allowlist)
            else:
                stats["skipped"] += 1
                continue

            if result["status"] == "fetched":
                stats["fetched"] += 1
                # Rate limiting: delay after successful fetch to be server-friendly
                # npm and PyPI both have rate limits (npm: 100/min, PyPI: 60/min)
                time.sleep(RATE_LIMIT_DELAY)  # Be server-friendly
            elif result["status"] == "cached":
                stats["cached"] += 1  # Shouldn't happen here but handle it
            elif result.get("reason") == "rate_limited":
                stats["errors"].append(f"{dep['name']}: Rate limited - backing off {RATE_LIMIT_BACKOFF}s")
                stats["skipped"] += 1
                # Set rate limit expiry for this service
                if dep["manager"] == "npm":
                    npm_rate_limited_until = time.time() + RATE_LIMIT_BACKOFF
                elif dep["manager"] == "py":
                    pypi_rate_limited_until = time.time() + RATE_LIMIT_BACKOFF
            else:
                stats["skipped"] += 1

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate" in error_msg.lower():
                stats["errors"].append(f"{dep['name']}: Rate limited - backing off {RATE_LIMIT_BACKOFF}s")
                # Set rate limit expiry for this service
                if dep["manager"] == "npm":
                    npm_rate_limited_until = time.time() + RATE_LIMIT_BACKOFF
                elif dep["manager"] == "py":
                    pypi_rate_limited_until = time.time() + RATE_LIMIT_BACKOFF
            else:
                stats["errors"].append(f"{dep['name']}: {error_msg}")

    return stats


def _check_cache_for_dep(dep: Dict[str, Any], output_dir: Path) -> Dict[str, bool]:
    """
    Quick cache check for a dependency without making network calls.
    Returns {"cached": True/False}
    """
    name = dep["name"]
    version = dep["version"]
    manager = dep["manager"]
    
    # Build the cache file path
    if manager == "npm":
        # Handle git versions
        if version.startswith("git") or "://" in version:
            import hashlib
            version_hash = hashlib.md5(version.encode()).hexdigest()[:8]
            safe_version = f"git-{version_hash}"
        else:
            safe_version = version.replace(":", "_").replace("/", "_").replace("\\", "_")
        safe_name = name.replace("@", "_at_").replace("/", "_")
        pkg_dir = output_dir / "npm" / f"{safe_name}@{safe_version}"
    elif manager == "py":
        safe_version = version.replace(":", "_").replace("/", "_").replace("\\", "_")
        safe_name = name.replace("/", "_").replace("\\", "_")
        pkg_dir = output_dir / "py" / f"{safe_name}@{safe_version}"
    else:
        return {"cached": False}
    
    doc_file = pkg_dir / "doc.md"
    meta_file = pkg_dir / "meta.json"
    
    # Check cache validity
    if doc_file.exists() and meta_file.exists():
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            # Cache for 7 days
            last_checked = datetime.fromisoformat(meta["last_checked"])
            if (datetime.now() - last_checked).days < 7:
                return {"cached": True}
        except (json.JSONDecodeError, KeyError):
            pass
    
    return {"cached": False}


def _fetch_npm_docs(
    dep: Dict[str, Any],
    output_dir: Path,
    allowlist: List[str]
) -> Dict[str, Any]:
    """Fetch documentation for an npm package."""
    name = dep["name"]
    version = dep["version"]
    
    # Validate package name
    if not validate_package_name(name, "npm"):
        return {"status": "skipped", "reason": "Invalid package name"}

    # Sanitize version for filesystem (handle git URLs)
    if version.startswith("git") or "://" in version:
        # For git dependencies, use a hash of the URL as version
        import hashlib
        version_hash = hashlib.md5(version.encode()).hexdigest()[:8]
        safe_version = f"git-{version_hash}"
    else:
        # For normal versions, just replace problematic characters
        safe_version = version.replace(":", "_").replace("/", "_").replace("\\", "_")

    # Create package-specific directory with sanitized name
    # Replace @ and / in scoped packages for filesystem safety
    safe_name = name.replace("@", "_at_").replace("/", "_")
    try:
        pkg_dir = output_dir / "npm" / f"{safe_name}@{safe_version}"
        pkg_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, SecurityError) as e:
        return {"status": "error", "error": f"Cannot create package directory: {e}"}

    doc_file = pkg_dir / "doc.md"
    meta_file = pkg_dir / "meta.json"

    # Check cache
    if doc_file.exists() and meta_file.exists():
        # Check if cache is still valid (simple time-based for now)
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            # Cache for 7 days
            last_checked = datetime.fromisoformat(meta["last_checked"])
            if (datetime.now() - last_checked).days < 7:
                return {"status": "cached"}
        except (json.JSONDecodeError, KeyError):
            pass  # Invalid cache, refetch

    # Fetch from registry with sanitized package name
    safe_url_name = sanitize_url_component(name)
    safe_url_version = sanitize_url_component(version)
    url = f"https://registry.npmjs.org/{safe_url_name}/{safe_url_version}"
    if not _is_url_allowed(url, allowlist):
        return {"status": "skipped", "reason": "URL not in allowlist"}

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

        readme = data.get("readme", "")
        repository = data.get("repository", {})
        homepage = data.get("homepage", "")

        # Priority 1: Try to get README from GitHub if available
        github_fetched = False
        if isinstance(repository, dict):
            repo_url = repository.get("url", "")
            github_readme = _fetch_github_readme(repo_url, allowlist)
            if github_readme and len(github_readme) > 500:  # Only use if substantial
                readme = github_readme
                github_fetched = True

        # Priority 2: If no good GitHub README, try homepage if it's GitHub
        if not github_fetched and homepage and "github.com" in homepage:
            github_readme = _fetch_github_readme(homepage, allowlist)
            if github_readme and len(github_readme) > 500:
                readme = github_readme
                github_fetched = True

        # Priority 3: Use npm README if it's substantial
        if not github_fetched and len(readme) < 500:
            # The npm README is too short, try to enhance it
            readme = _enhance_npm_readme(data, readme)

        # Write documentation
        with open(doc_file, "w", encoding="utf-8") as f:
            f.write(f"# {name}@{version}\n\n")
            f.write(f"**Package**: [{name}](https://www.npmjs.com/package/{name})\n")
            f.write(f"**Version**: {version}\n")
            if homepage:
                f.write(f"**Homepage**: {homepage}\n")
            f.write("\n---\n\n")
            f.write(readme)

            # Add usage examples if not in README
            if "## Usage" not in readme and "## Example" not in readme:
                f.write("\n\n## Installation\n\n```bash\nnpm install {name}\n```\n".format(name=name))

        # Write metadata
        meta = {
            "source_url": url,
            "last_checked": datetime.now().isoformat(),
            "etag": response.headers.get("ETag"),
            "repository": repository,
            "from_github": github_fetched
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return {"status": "fetched"}

    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"status": "error", "reason": "rate_limited", "error": "HTTP 429: Rate limited"}
        return {"status": "error", "error": f"HTTP {e.code}: {str(e)}"}
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        return {"status": "error", "error": str(e)}


def _fetch_pypi_docs(
    dep: Dict[str, Any],
    output_dir: Path,
    allowlist: List[str]
) -> Dict[str, Any]:
    """Fetch documentation for a PyPI package."""
    name = dep["name"].strip()  # Strip any whitespace from name
    version = dep["version"]
    
    # Validate package name
    if not validate_package_name(name, "py"):
        return {"status": "skipped", "reason": "Invalid package name"}

    # Sanitize package name for URL
    safe_url_name = sanitize_url_component(name)
    
    # Handle special versions
    if version in ["latest", "git"]:
        # For latest, fetch current version first
        if version == "latest":
            url = f"https://pypi.org/pypi/{safe_url_name}/json"
        else:
            return {"status": "skipped", "reason": "git dependency"}
    else:
        safe_url_version = sanitize_url_component(version)
        url = f"https://pypi.org/pypi/{safe_url_name}/{safe_url_version}/json"

    if not _is_url_allowed(url, allowlist):
        return {"status": "skipped", "reason": "URL not in allowlist"}

    # Sanitize version for filesystem
    safe_version = version.replace(":", "_").replace("/", "_").replace("\\", "_")
    
    # Create package-specific directory with sanitized name
    safe_name = name.replace("/", "_").replace("\\", "_")
    try:
        pkg_dir = output_dir / "py" / f"{safe_name}@{safe_version}"
        pkg_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, SecurityError) as e:
        return {"status": "error", "error": f"Cannot create package directory: {e}"}

    doc_file = pkg_dir / "doc.md"
    meta_file = pkg_dir / "meta.json"

    # Check cache
    if doc_file.exists() and meta_file.exists():
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            last_checked = datetime.fromisoformat(meta["last_checked"])
            if (datetime.now() - last_checked).days < 7:
                return {"status": "cached"}
        except (json.JSONDecodeError, KeyError):
            pass

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

        info = data.get("info", {})
        description = info.get("description", "")
        summary = info.get("summary", "")

        # Priority 1: Try to get README from project URLs (GitHub, GitLab, etc.)
        github_fetched = False
        project_urls = info.get("project_urls", {})

        # Check all possible URL sources for GitHub
        all_urls = []
        for key, proj_url in project_urls.items():
            if proj_url:
                all_urls.append(proj_url)

        # Also check home_page and download_url
        home_page = info.get("home_page", "")
        if home_page:
            all_urls.append(home_page)
        download_url = info.get("download_url", "")
        if download_url:
            all_urls.append(download_url)

        # Try GitHub first
        for url in all_urls:
            if "github.com" in url.lower():
                github_readme = _fetch_github_readme(url, allowlist)
                if github_readme and len(github_readme) > 500:
                    description = github_readme
                    github_fetched = True
                    break

        # Priority 2: Try ReadTheDocs if available
        if not github_fetched:
            for url in all_urls:
                if "readthedocs" in url.lower():
                    rtd_content = _fetch_readthedocs(url, allowlist)
                    if rtd_content and len(rtd_content) > 500:
                        description = rtd_content
                        github_fetched = True  # Mark as fetched from external source
                        break

        # Priority 3: Try to scrape PyPI web page (not API) for full README
        if not github_fetched and len(description) < 1000:
            pypi_readme = _fetch_pypi_web_readme(name, version, allowlist)
            if pypi_readme and len(pypi_readme) > len(description):
                description = pypi_readme
                github_fetched = True  # Mark as fetched from external source

        # Priority 4: Use PyPI description (often contains full README)
        # PyPI descriptions can be quite good if properly uploaded
        if not github_fetched and len(description) < 500 and summary:
            # If description is too short, enhance it
            description = _enhance_pypi_description(info, description, summary)

        # Try to crawl documentation site if available
        crawled_docs = {}
        doc_site_url = None

        # Look for ReadTheDocs or other doc sites in project URLs
        for key, proj_url in project_urls.items():
            if proj_url and ("readthedocs" in proj_url.lower() or "docs" in key.lower()):
                # Found a documentation site - try to crawl it
                doc_site_url = proj_url
                try:
                    # Add common doc sites to allowlist
                    extended_allowlist = allowlist + [
                        "https://docs.python.org/",
                        f"https://{name}.readthedocs.io/",
                        f"https://{name}.readthedocs.org/",
                        f"https://{name}.github.io/",
                        f"https://www.{name}.org/",
                    ]
                    crawled_docs = _crawl_docs_site(
                        proj_url.rstrip("/"),
                        name,
                        version,
                        max_pages=5,  # Limit to 5 pages for PyPI
                        allowlist=extended_allowlist
                    )
                    if crawled_docs:
                        break  # Successfully crawled
                except Exception:
                    pass  # Crawling failed, fall back to README only

        # Write documentation - multiple files if crawled, single file otherwise
        source_urls = {}

        if crawled_docs:
            # Multi-file storage: README.md + crawled pages
            # Write README.md
            readme_file = pkg_dir / "README.md"
            with open(readme_file, "w", encoding="utf-8") as f:
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

            source_urls["README"] = url  # PyPI API URL

            # Write crawled documentation pages
            for page_name, content in crawled_docs.items():
                page_file = pkg_dir / f"{page_name}.md"
                with open(page_file, "w", encoding="utf-8") as f:
                    f.write(f"# {name}@{version} - {page_name.replace('_', ' ').title()}\n\n")
                    f.write(content)
                source_urls[page_name] = doc_site_url or "crawled"

        else:
            # Single-file storage (legacy format for backward compatibility)
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

                if len(description) < 200:
                    f.write(f"\n\n## Basic Usage\n\n```python\nimport {name.replace('-', '_')}\n```\n")

            source_urls["doc"] = url

        # Write metadata
        meta = {
            "package": name,
            "version": version,
            "ecosystem": "py",
            "source_url": url,
            "source_urls": source_urls,
            "file_count": len(source_urls),
            "last_checked": datetime.now().isoformat(),
            "etag": response.headers.get("ETag"),
            "project_urls": project_urls,
            "from_github": github_fetched,
            "crawled": len(crawled_docs) > 0
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return {"status": "fetched"}

    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"status": "error", "reason": "rate_limited", "error": "HTTP 429: Rate limited"}
        return {"status": "error", "error": f"HTTP {e.code}: {str(e)}"}
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        return {"status": "error", "error": str(e)}


def _fetch_github_readme(repo_url: str, allowlist: List[str]) -> Optional[str]:
    """
    Fetch README from GitHub repository.
    Converts repository URL to raw GitHub URL for README.
    """
    if not repo_url:
        return None

    # Extract owner/repo from various GitHub URL formats
    patterns = [
        r'github\.com[:/]([^/]+)/([^/\s]+)',
        r'git\+https://github\.com/([^/]+)/([^/\s]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, repo_url)
        if match:
            owner, repo = match.groups()
            # Clean repo name
            repo = repo.replace(".git", "")

            # Try common README filenames
            readme_files = ["README.md", "readme.md", "README.rst", "README.txt"]

            # Sanitize owner and repo for URL
            safe_owner = sanitize_url_component(owner)
            safe_repo = sanitize_url_component(repo)

            for readme_name in readme_files:
                safe_readme = sanitize_url_component(readme_name)
                raw_url = f"https://raw.githubusercontent.com/{safe_owner}/{safe_repo}/main/{safe_readme}"

                if not _is_url_allowed(raw_url, allowlist):
                    continue

                try:
                    with urllib.request.urlopen(raw_url, timeout=5) as response:
                        return response.read().decode("utf-8")
                except urllib.error.HTTPError:
                    # Try master branch
                    raw_url = f"https://raw.githubusercontent.com/{safe_owner}/{safe_repo}/master/{safe_readme}"
                    try:
                        with urllib.request.urlopen(raw_url, timeout=5) as response:
                            return response.read().decode("utf-8")
                    except urllib.error.URLError:
                        continue
                except urllib.error.URLError:
                    continue

    return None


def _is_url_allowed(url: str, allowlist: List[str]) -> bool:
    """Check if URL is in the allowlist."""
    for allowed in allowlist:
        if url.startswith(allowed):
            return True
    return False


def _enhance_npm_readme(data: Dict[str, Any], readme: str) -> str:
    """Enhance minimal npm README with package metadata."""
    enhanced = readme if readme else ""

    # Add description if not in README
    description = data.get("description", "")
    if description and description not in enhanced:
        enhanced = f"{description}\n\n{enhanced}"

    # Add keywords
    keywords = data.get("keywords", [])
    if keywords and "keywords" not in enhanced.lower():
        enhanced += f"\n\n## Keywords\n\n{', '.join(keywords)}"

    # Add main entry point info
    main = data.get("main", "")
    if main:
        enhanced += f"\n\n## Entry Point\n\nMain file: `{main}`"

    # Add dependencies info if substantial
    deps = data.get("dependencies", {})
    if len(deps) > 0 and len(deps) <= 10:  # Only if reasonable number
        enhanced += "\n\n## Dependencies\n\n"
        for dep, ver in deps.items():
            enhanced += f"- {dep}: {ver}\n"

    return enhanced


def _fetch_and_convert_html(url: str, allowlist: List[str], timeout: int = 10) -> Optional[str]:
    """
    Fetch HTML from URL and convert to clean markdown using BeautifulSoup.

    This replaces the old regex-based HTML parsing with proper DOM parsing.
    Falls back to regex if BeautifulSoup is not available.

    Args:
        url: URL to fetch
        allowlist: List of allowed URL prefixes
        timeout: Request timeout in seconds

    Returns:
        Cleaned markdown content or None on error
    """
    if not url or not _is_url_allowed(url, allowlist):
        return None

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; TheAuditor/1.0)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html_content = response.read().decode("utf-8", errors="ignore")

        if not BEAUTIFULSOUP_AVAILABLE:
            # Fallback to old regex method if BeautifulSoup not installed
            return _convert_html_regex(html_content)

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
            element.decompose()

        # Try to find main content area (common selectors)
        main_content = None
        content_selectors = [
            'article',
            'main',
            '[role="main"]',
            '.document',  # ReadTheDocs
            '.rst-content',  # ReadTheDocs
            '.project-description',  # PyPI
            '.content',
            '.main-content',
            '#content',
            '#main'
        ]

        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break

        # If no main content found, use body
        if not main_content:
            main_content = soup.find('body')

        if not main_content:
            return None

        # Convert to markdown using markdownify
        markdown = md(
            str(main_content),
            heading_style="ATX",  # Use # style headings
            bullets="-",  # Use - for lists
            code_language_callback=lambda el: el.get('class', [''])[0] if el.get('class') else '',
            strip=['a']  # Remove link formatting but keep text
        )

        # Clean up excessive whitespace
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        markdown = markdown.strip()

        return markdown if len(markdown) > 100 else None

    except Exception:
        return None


def _convert_html_regex(html_content: str) -> str:
    """
    Fallback regex-based HTML to markdown conversion.
    Used when BeautifulSoup is not available.
    """
    # Remove script and style tags
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)

    # Convert basic HTML tags to markdown
    html_content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<[^>]+>', '', html_content)

    # Clean up whitespace
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)

    return html_content.strip()


def _crawl_docs_site(
    base_url: str,
    package_name: str,
    version: str,
    max_pages: int = 10,
    allowlist: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Crawl documentation site for multiple pages.

    Fetches priority pages (quickstart, API, examples, etc.) in order,
    trying multiple version-specific URL patterns for each.

    Args:
        base_url: Base documentation URL (e.g., https://flask.palletsprojects.com)
        package_name: Package name (e.g., "flask")
        version: Semantic version (e.g., "3.1.0")
        max_pages: Maximum pages to fetch (default 10)
        allowlist: List of allowed URL prefixes (uses DEFAULT_ALLOWLIST if None)

    Returns:
        Dict mapping page names to markdown content:
        {
            "README": "...",
            "quickstart": "...",
            "api_reference": "..."
        }
    """
    if allowlist is None:
        allowlist = DEFAULT_ALLOWLIST

    results: Dict[str, str] = {}
    pages_fetched = 0

    # Priority pages to fetch (in order of importance)
    priority_pages = [
        ("quickstart", ["quickstart", "getting-started", "tutorial", "getting_started"]),
        ("api_reference", ["api", "api-reference", "reference", "api_reference"]),
        ("guide", ["guide", "user-guide", "userguide", "user_guide"]),
        ("examples", ["examples", "example", "cookbook"]),
        ("migration", ["migration", "upgrading", "changelog", "changes", "whatsnew"]),
    ]

    # Extract version components for URL patterns
    version_parts = version.split(".")
    major = version_parts[0] if len(version_parts) > 0 else "1"
    major_minor = ".".join(version_parts[:2]) if len(version_parts) >= 2 else version

    for page_canonical_name, page_variants in priority_pages:
        if pages_fetched >= max_pages:
            break

        # Try each variant of the page name
        for page_name in page_variants:
            if pages_fetched >= max_pages:
                break

            # Try multiple URL patterns for this page
            url_patterns = [
                f"{base_url}/en/{version}/{page_name}/",       # /en/3.1.0/quickstart/
                f"{base_url}/en/{major_minor}/{page_name}/",   # /en/3.1/quickstart/
                f"{base_url}/en/{major_minor}.x/{page_name}/", # /en/3.1.x/quickstart/ (Flask style)
                f"{base_url}/en/{major}.x/{page_name}/",       # /en/3.x/quickstart/
                f"{base_url}/{version}/{page_name}/",          # /3.1.0/quickstart/
                f"{base_url}/{major_minor}/{page_name}/",      # /3.1/quickstart/
                f"{base_url}/v{version}/{page_name}/",         # /v3.1.0/quickstart/
                f"{base_url}/v{major_minor}/{page_name}/",     # /v3.1/quickstart/
                f"{base_url}/docs/{page_name}/",               # /docs/quickstart/
                f"{base_url}/user/{page_name}/",               # /user/quickstart/
                f"{base_url}/{page_name}.html",                # /quickstart.html
                f"{base_url}/docs/{page_name}.html",           # /docs/quickstart.html
            ]

            for url in url_patterns:
                if not _is_url_allowed(url, allowlist):
                    continue

                # Try to fetch and convert this URL
                markdown = _fetch_and_convert_html(url, allowlist, timeout=10)

                if markdown and len(markdown) > 200:  # Only accept substantial content
                    # Store under canonical name
                    results[page_canonical_name] = markdown
                    pages_fetched += 1

                    # Rate limiting - be server-friendly
                    time.sleep(0.5)
                    break  # Found working URL for this page, move to next page

            # If we found this page variant, stop trying other variants
            if page_canonical_name in results:
                break

    return results


def _fetch_readthedocs(url: str, allowlist: List[str]) -> Optional[str]:
    """
    Fetch documentation from ReadTheDocs.
    Tries to get the main index page content.
    """
    if not url or not _is_url_allowed(url, allowlist):
        return None

    # Ensure we're getting the latest version
    if not url.endswith("/"):
        url += "/"

    # Try to fetch the main page
    try:
        # Add en/latest if not already in URL
        if "/en/latest" not in url and "/en/stable" not in url:
            url = url.rstrip("/") + "/en/latest/"

        with urllib.request.urlopen(url, timeout=10) as response:
            html_content = response.read().decode("utf-8")

        # Basic HTML to markdown conversion (very simplified)
        # Remove script and style tags
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)

        # Extract main content (look for common RTD content divs)
        content_match = re.search(r'<div[^>]*class="[^"]*document[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if content_match:
            html_content = content_match.group(1)

        # Convert basic HTML tags to markdown
        html_content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', html_content)
        html_content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', html_content)
        html_content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', html_content)
        html_content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html_content)
        html_content = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_content)
        html_content = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', html_content)
        html_content = re.sub(r'<[^>]+>', '', html_content)  # Remove remaining HTML tags

        # Clean up whitespace
        html_content = re.sub(r'\n{3,}', '\n\n', html_content)

        return html_content.strip()
    except Exception:
        return None


def _fetch_pypi_web_readme(name: str, version: str, allowlist: List[str]) -> Optional[str]:
    """
    Fetch the rendered README from PyPI's web interface.
    The web interface shows the full README that's often missing from the API.
    """
    # Validate package name
    if not validate_package_name(name, "py"):
        return None
    
    # Sanitize for URL
    safe_name = sanitize_url_component(name)
    safe_version = sanitize_url_component(version)
    
    # PyPI web URLs
    urls_to_try = [
        f"https://pypi.org/project/{safe_name}/{safe_version}/",
        f"https://pypi.org/project/{safe_name}/"
    ]

    for url in urls_to_try:
        if not _is_url_allowed(url, allowlist):
            continue

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; TheAuditor/1.0)'
            })
            with urllib.request.urlopen(req, timeout=10) as response:
                html_content = response.read().decode("utf-8")

            # Look for the project description div
            # PyPI uses a specific class for the README content
            readme_match = re.search(
                r'<div[^>]*class="[^"]*project-description[^"]*"[^>]*>(.*?)</div>',
                html_content,
                re.DOTALL | re.IGNORECASE
            )

            if not readme_match:
                # Try alternative patterns
                readme_match = re.search(
                    r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>',
                    html_content,
                    re.DOTALL | re.IGNORECASE
                )

            if readme_match:
                readme_html = readme_match.group(1)

                # Convert HTML to markdown (simplified)
                # Headers
                readme_html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', readme_html, flags=re.IGNORECASE)
                readme_html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', readme_html, flags=re.IGNORECASE)
                readme_html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', readme_html, flags=re.IGNORECASE)

                # Code blocks
                readme_html = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'```\n\1\n```', readme_html, flags=re.DOTALL | re.IGNORECASE)
                readme_html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', readme_html, flags=re.IGNORECASE)

                # Lists
                readme_html = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', readme_html, flags=re.IGNORECASE)

                # Links
                readme_html = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', readme_html, flags=re.IGNORECASE)

                # Paragraphs and line breaks
                readme_html = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', readme_html, flags=re.DOTALL | re.IGNORECASE)
                readme_html = re.sub(r'<br[^>]*>', '\n', readme_html, flags=re.IGNORECASE)

                # Remove remaining HTML tags
                readme_html = re.sub(r'<[^>]+>', '', readme_html)

                # Decode HTML entities
                readme_html = readme_html.replace('&lt;', '<')
                readme_html = readme_html.replace('&gt;', '>')
                readme_html = readme_html.replace('&amp;', '&')
                readme_html = readme_html.replace('&quot;', '"')
                readme_html = readme_html.replace('&#39;', "'")

                # Clean up whitespace
                readme_html = re.sub(r'\n{3,}', '\n\n', readme_html)
                readme_html = readme_html.strip()

                if len(readme_html) > 100:  # Only return if we got substantial content
                    return readme_html
        except Exception:
            continue

    return None


def _enhance_pypi_description(info: Dict[str, Any], description: str, summary: str) -> str:
    """Enhance minimal PyPI description with package metadata."""
    enhanced = description if description else ""

    # Start with summary if description is empty
    if not enhanced and summary:
        enhanced = f"{summary}\n\n"

    # Add author info
    author = info.get("author", "")
    author_email = info.get("author_email", "")
    if author and "author" not in enhanced.lower():
        author_info = f"\n\n## Author\n\n{author}"
        if author_email:
            author_info += f" ({author_email})"
        enhanced += author_info

    # Add license
    license_info = info.get("license", "")
    if license_info and "license" not in enhanced.lower():
        enhanced += f"\n\n## License\n\n{license_info}"

    # Add classifiers (limited)
    classifiers = info.get("classifiers", [])
    relevant_classifiers = [
        c for c in classifiers
        if "Programming Language" in c or "Framework" in c or "Topic" in c
    ][:5]  # Limit to 5
    if relevant_classifiers:
        enhanced += "\n\n## Classifiers\n\n"
        for classifier in relevant_classifiers:
            enhanced += f"- {classifier}\n"

    # Add requires_python if specified
    requires_python = info.get("requires_python", "")
    if requires_python:
        enhanced += f"\n\n## Python Version\n\nRequires Python {requires_python}"

    return enhanced


def check_latest(
    deps: List[Dict[str, Any]],
    allow_net: bool = True,
    offline: bool = False,
    output_path: str = "./.pf/deps_latest.json"
) -> Dict[str, Any]:
    """
    Check latest versions and compare to locked versions.
    
    This is a wrapper around deps.check_latest_versions for consistency.
    """
    from .deps import check_latest_versions, write_deps_latest_json

    if offline or not allow_net:
        return {
            "mode": "offline",
            "checked": 0,
            "outdated": 0
        }

    latest_info = check_latest_versions(deps, allow_net=allow_net, offline=offline)

    if latest_info:
        # Sanitize output path before writing
        try:
            safe_output_path = str(sanitize_path(output_path, "."))
            write_deps_latest_json(latest_info, safe_output_path)
        except SecurityError as e:
            return {
                "mode": "error",
                "error": f"Invalid output path: {e}",
                "checked": 0,
                "outdated": 0
            }

    outdated = sum(1 for info in latest_info.values() if info["is_outdated"])

    return {
        "mode": "online",
        "checked": len(latest_info),
        "outdated": outdated,
        "output": output_path
    }
