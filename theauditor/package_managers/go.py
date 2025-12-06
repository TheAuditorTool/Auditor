"""Go package manager implementation.

Handles go.mod files for:
- Parsing module dependencies
- Fetching latest versions from proxy.golang.org
- Fetching documentation from pkg.go.dev
- Upgrading go.mod versions
"""

from __future__ import annotations

import platform
import re
from pathlib import Path
from typing import Any

from theauditor import __version__
from theauditor.pipeline.ui import console
from theauditor.utils.logging import logger
from theauditor.utils.rate_limiter import get_rate_limiter

from .base import BasePackageManager, Dependency

IS_WINDOWS = platform.system() == "Windows"


def _encode_go_module(module: str) -> str:
    """Encode Go module path for proxy URL.

    Per Go proxy spec: uppercase letters become !lowercase.
    Example: github.com/Azure/azure-sdk-for-go -> github.com/!azure/azure-sdk-for-go
    """
    result = []
    for char in module:
        if char.isupper():
            result.append("!")
            result.append(char.lower())
        else:
            result.append(char)
    return "".join(result)


class GoPackageManager(BasePackageManager):
    """Go package manager for go.mod files."""

    @property
    def manager_name(self) -> str:
        return "go"

    @property
    def file_patterns(self) -> list[str]:
        return ["go.mod"]

    @property
    def registry_url(self) -> str | None:
        return "https://proxy.golang.org/"

    def parse_manifest(self, path: Path) -> list[Dependency]:
        """Parse go.mod file for dependencies.

        Args:
            path: Path to go.mod file

        Returns:
            List of Dependency objects with guaranteed structure.
        """
        deps: list[Dependency] = []
        content = path.read_text(encoding="utf-8")

        module_match = re.search(r"^module\s+(\S+)", content, re.MULTILINE)
        module_path = module_match.group(1) if module_match else ""

        go_version_match = re.search(r"^go\s+(\d+\.\d+)", content, re.MULTILINE)
        go_version = go_version_match.group(1) if go_version_match else ""

        require_block_match = re.search(r"require\s*\((.*?)\)", content, re.DOTALL)
        if require_block_match:
            for line in require_block_match.group(1).strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("//"):
                    dep = self._parse_require_line(line, str(path), module_path, go_version)
                    if dep:
                        deps.append(dep)

        for match in re.finditer(r"^require\s+([a-zA-Z][\S]*)\s+(v[\S]+)", content, re.MULTILINE):
            deps.append(
                Dependency(
                    name=match.group(1),
                    version=match.group(2),
                    manager="go",
                    source=str(path),
                    is_indirect=False,
                    module_path=module_path,
                    go_version=go_version,
                )
            )

        return deps

    def _parse_require_line(
        self, line: str, source: str, module_path: str, go_version: str
    ) -> Dependency | None:
        """Parse a single require line from go.mod."""

        if "//" in line:
            code_part = line.split("//")[0].strip()
            is_indirect = "indirect" in line
        else:
            code_part = line.strip()
            is_indirect = False

        parts = code_part.split()
        if len(parts) >= 2:
            return Dependency(
                name=parts[0],
                version=parts[1],
                manager="go",
                source=source,
                is_indirect=is_indirect,
                module_path=module_path,
                go_version=go_version,
            )

        return None

    async def fetch_latest_async(
        self,
        client: Any,
        dep: Dependency,
        allow_prerelease: bool = False,
    ) -> str | None:
        """Fetch latest Go module version from proxy.golang.org.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency object
            allow_prerelease: Include pre-release versions (unused for Go)

        Returns:
            Latest version string or None
        """

        encoded_module = _encode_go_module(dep.name)

        limiter = get_rate_limiter("go")
        await limiter.acquire()

        url = f"https://proxy.golang.org/{encoded_module}/@latest"
        headers = {"User-Agent": f"TheAuditor/{__version__} (dependency checker)"}
        response = await client.get(url, headers=headers, timeout=10.0)

        if response.status_code != 200:
            return None

        data = response.json()
        return data.get("Version")

    async def fetch_docs_async(
        self,
        client: Any,
        dep: Dependency,
        output_path: Path,
        allowlist: list[str],
    ) -> str:
        """Fetch Go module documentation from pkg.go.dev.

        Args:
            client: httpx.AsyncClient instance
            dep: Dependency object
            output_path: Directory to write documentation to
            allowlist: List of module names to fetch (empty = all)

        Returns:
            Status: 'fetched', 'cached', 'skipped', or 'error'
        """
        module = dep.name
        version = dep.version or "latest"

        if allowlist and module not in allowlist:
            return "skipped"

        safe_name = module.replace("/", "_")
        doc_file = output_path / f"{safe_name}.md"
        if doc_file.exists():
            return "cached"

        limiter = get_rate_limiter("go")
        await limiter.acquire()

        try:
            url = f"https://pkg.go.dev/{module}@{version}"
            response = await client.get(url, timeout=10.0, follow_redirects=True)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch docs for {module}: HTTP {response.status_code}")
                return "error"

            html = response.text

            markdown = self._extract_go_docs(html)

            if markdown:
                output_path.mkdir(parents=True, exist_ok=True)
                doc_file.write_text(markdown, encoding="utf-8")
                return "fetched"

            logger.info(f"No documentation section found for {module}")
            return "skipped"

        except Exception as e:
            logger.warning(f"Failed to fetch docs for {module}: {e}")
            return "error"

    def _extract_go_docs(self, html: str) -> str | None:
        """Extract Go documentation from pkg.go.dev HTML using regex.

        Uses regex for HTML->Markdown conversion. May break if pkg.go.dev
        changes DOM structure. Acceptable tradeoff: docs fetching is non-critical,
        re-running 'aud full' fixes stale output.
        """

        match = re.search(
            r'<section[^>]*class="[^"]*Documentation[^"]*"[^>]*>(.*?)</section>',
            html,
            re.DOTALL | re.IGNORECASE,
        )

        if not match:
            match = re.search(
                r'<div[^>]*class="[^"]*Documentation-content[^"]*"[^>]*>(.*?)</div>',
                html,
                re.DOTALL | re.IGNORECASE,
            )

        if not match:
            return None

        content = match.group(1)

        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)

        content = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", content, flags=re.DOTALL)
        content = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", content, flags=re.DOTALL)
        content = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n", content, flags=re.DOTALL)

        content = re.sub(r"<pre[^>]*>(.*?)</pre>", r"```\n\1\n```\n", content, flags=re.DOTALL)
        content = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", content, flags=re.DOTALL)

        content = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", content, flags=re.DOTALL)

        content = re.sub(r"<[^>]+>", "", content)

        content = re.sub(r"\n{3,}", "\n\n", content)
        content = content.strip()

        return content if content else None

    def upgrade_file(
        self,
        path: Path,
        latest_info: dict[str, dict[str, Any]],
        deps: list[Dependency],
    ) -> int:
        """Upgrade go.mod to latest versions.

        Note: Caller is responsible for creating backup before calling.

        Args:
            path: Path to go.mod
            latest_info: Dict mapping dep keys to version info
            deps: List of Dependency objects

        Returns:
            Count of dependencies upgraded
        """
        content = path.read_text(encoding="utf-8")
        original = content
        count = 0
        upgraded = {}

        for dep in deps:
            if dep.source != str(path):
                continue

            if dep.is_indirect:
                continue

            key = f"go:{dep.name}:{dep.version}"
            info = latest_info.get(key)
            if not info or not info.get("latest") or not info.get("is_outdated"):
                continue

            old_version = dep.version
            new_version = info["latest"]
            module = dep.name

            escaped_module = re.escape(module)
            escaped_old_version = re.escape(old_version)

            pattern = rf"({escaped_module}\s+){escaped_old_version}(\s*(?://.*)?$)"
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(
                    pattern,
                    rf"\g<1>{new_version}\g<2>",
                    content,
                    flags=re.MULTILINE,
                )
                upgraded[module] = (old_version, new_version)
                count += 1

        if content != original:
            path.write_text(content, encoding="utf-8")

        check_mark = "[OK]" if IS_WINDOWS else "[OK]"
        arrow = "->" if IS_WINDOWS else "->"
        for module, (old_ver, new_ver) in upgraded.items():
            console.print(f"  {check_mark} {module}: {old_ver} {arrow} {new_ver}", highlight=False)

        return count
