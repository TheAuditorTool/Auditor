"""Documentation summarizer for creating concise doc capsules."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def summarize_docs(
    docs_dir: str = "./.pf/context/docs",
    output_dir: str = "./.pf/context/doc_capsules",
    workset_path: Optional[str] = None,
    max_capsule_lines: int = 50
) -> Dict[str, Any]:
    """
    Generate concise doc capsules from fetched documentation.
    
    Args:
        docs_dir: Directory containing fetched docs
        output_dir: Directory for output capsules
        workset_path: Optional workset to filter relevant deps
        max_capsule_lines: Maximum lines per capsule
    
    Returns:
        Summary statistics
    """
    docs_path = Path(docs_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load workset if provided
    relevant_deps = None
    if workset_path and Path(workset_path).exists():
        relevant_deps = _load_workset_deps(workset_path)
    
    stats = {
        "total_docs": 0,
        "capsules_created": 0,
        "skipped": 0,
        "errors": []
    }
    
    capsules_index = []
    
    # Process npm docs
    npm_dir = docs_path / "npm"
    if npm_dir.exists():
        for pkg_dir in npm_dir.iterdir():
            if not pkg_dir.is_dir():
                continue
            
            # Extract package name and version
            pkg_info = pkg_dir.name  # format: name@version
            if "@" not in pkg_info:
                stats["skipped"] += 1
                continue
            
            name_version = pkg_info.rsplit("@", 1)
            if len(name_version) != 2:
                stats["skipped"] += 1
                continue
            
            name, version = name_version
            
            # Check if in workset
            if relevant_deps and f"npm:{name}" not in relevant_deps:
                stats["skipped"] += 1
                continue
            
            stats["total_docs"] += 1
            
            # Create capsule
            doc_file = pkg_dir / "doc.md"
            meta_file = pkg_dir / "meta.json"
            
            if doc_file.exists():
                try:
                    capsule = _create_capsule(
                        doc_file, meta_file, name, version, "npm", max_capsule_lines
                    )
                    
                    # Write capsule
                    capsule_file = output_path / f"npm__{name}@{version}.md"
                    with open(capsule_file, "w", encoding="utf-8") as f:
                        f.write(capsule)
                    
                    capsules_index.append({
                        "name": name,
                        "version": version,
                        "ecosystem": "npm",
                        "path": str(capsule_file.relative_to(output_path))
                    })
                    
                    stats["capsules_created"] += 1
                    
                except Exception as e:
                    stats["errors"].append(f"{name}@{version}: {str(e)}")
    
    # Process Python docs
    py_dir = docs_path / "py"
    if py_dir.exists():
        for pkg_dir in py_dir.iterdir():
            if not pkg_dir.is_dir():
                continue
            
            # Extract package name and version
            pkg_info = pkg_dir.name  # format: name@version
            if "@" not in pkg_info:
                stats["skipped"] += 1
                continue
            
            name_version = pkg_info.rsplit("@", 1)
            if len(name_version) != 2:
                stats["skipped"] += 1
                continue
            
            name, version = name_version
            
            # Check if in workset
            if relevant_deps and f"py:{name}" not in relevant_deps:
                stats["skipped"] += 1
                continue
            
            stats["total_docs"] += 1
            
            # Create capsule
            doc_file = pkg_dir / "doc.md"
            meta_file = pkg_dir / "meta.json"
            
            if doc_file.exists():
                try:
                    capsule = _create_capsule(
                        doc_file, meta_file, name, version, "py", max_capsule_lines
                    )
                    
                    # Write capsule
                    capsule_file = output_path / f"py__{name}@{version}.md"
                    with open(capsule_file, "w", encoding="utf-8") as f:
                        f.write(capsule)
                    
                    capsules_index.append({
                        "name": name,
                        "version": version,
                        "ecosystem": "py",
                        "path": str(capsule_file.relative_to(output_path))
                    })
                    
                    stats["capsules_created"] += 1
                    
                except Exception as e:
                    stats["errors"].append(f"{name}@{version}: {str(e)}")
    
    # Write index
    index_file = output_path.parent / "doc_index.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump({
            "created_at": datetime.now().isoformat(),
            "capsules": capsules_index,
            "stats": stats
        }, f, indent=2)
    
    return stats


def _load_workset_deps(workset_path: str) -> Set[str]:
    """
    Load relevant dependencies from workset.
    Returns set of "manager:name" keys.
    """
    relevant = set()
    
    try:
        with open(workset_path, encoding="utf-8") as f:
            workset = json.load(f)
        
        # Extract imported packages from workset files
        # This is a simplified version - would need more sophisticated parsing
        for file_info in workset.get("files", []):
            path = file_info.get("path", "")
            
            # Simple heuristic: look at file extension
            if path.endswith((".js", ".ts", ".jsx", ".tsx")):
                # Would parse imports/requires
                # For now, include all npm deps
                relevant.add("npm:*")
            elif path.endswith(".py"):
                # Would parse imports
                # For now, include all py deps
                relevant.add("py:*")
    
    except (json.JSONDecodeError, KeyError):
        pass
    
    # If we couldn't determine specific deps, include all
    if not relevant or "npm:*" in relevant or "py:*" in relevant:
        return set()  # Empty set means include all
    
    return relevant


def _create_capsule(
    doc_file: Path,
    meta_file: Path,
    name: str,
    version: str,
    ecosystem: str,
    max_lines: int
) -> str:
    """Create a concise capsule from documentation."""
    
    # Read documentation
    with open(doc_file, encoding="utf-8") as f:
        content = f.read()
    
    # Read metadata
    meta = {}
    if meta_file.exists():
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
        except json.JSONDecodeError:
            pass
    
    # Extract key sections
    sections = {
        "init": _extract_initialization(content, ecosystem),
        "apis": _extract_top_apis(content),
        "examples": _extract_examples(content),
    }
    
    # Build capsule
    capsule_lines = [
        f"# {name}@{version} ({ecosystem})",
        "",
        "## Quick Start",
        ""
    ]
    
    if sections["init"]:
        capsule_lines.extend(sections["init"][:10])  # Limit lines
        capsule_lines.append("")
    elif content:  # If no structured init but has content, add some raw content
        content_lines = content.split("\n")[:10]
        capsule_lines.extend(content_lines)
        capsule_lines.append("")
    
    if sections["apis"]:
        capsule_lines.append("## Top APIs")
        capsule_lines.append("")
        capsule_lines.extend(sections["apis"][:15])  # Limit lines
        capsule_lines.append("")
    
    if sections["examples"]:
        capsule_lines.append("## Examples")
        capsule_lines.append("")
        capsule_lines.extend(sections["examples"][:15])  # Limit lines
        capsule_lines.append("")
    
    # Add reference to full documentation
    capsule_lines.append("## 📄 Full Documentation Available")
    capsule_lines.append("")
    # Calculate relative path from project root
    full_doc_path = f"./.pf/context/docs/{ecosystem}/{name}@{version}/doc.md"
    capsule_lines.append(f"**Full content**: `{full_doc_path}`")
    
    # Count lines in full doc if it exists
    if doc_file.exists():
        try:
            with open(doc_file, encoding="utf-8") as f:
                line_count = len(f.readlines())
            capsule_lines.append(f"**Size**: {line_count} lines")
        except Exception:
            pass
    
    capsule_lines.append("")
    
    # Add source info
    capsule_lines.append("## Source")
    capsule_lines.append("")
    capsule_lines.append(f"- URL: {meta.get('source_url', '')}")
    capsule_lines.append(f"- Fetched: {meta.get('last_checked', '')}")
    
    # Truncate if too long
    if len(capsule_lines) > max_lines:
        # Keep the full doc reference even when truncating
        keep_lines = capsule_lines[:max_lines-7]  # Leave room for reference and truncation
        ref_lines = [l for l in capsule_lines if "Full Documentation Available" in l or "Full content" in l or "Size" in l]
        capsule_lines = keep_lines + ["", "...","(truncated)", ""] + ref_lines
    
    return "\n".join(capsule_lines)


def _extract_initialization(content: str, ecosystem: str) -> List[str]:
    """Extract initialization/installation snippets."""
    lines = []
    
    # Look for installation section
    install_patterns = [
        r"## Install\w*",
        r"## Getting Started",
        r"## Quick Start",
        r"### Install\w*",
    ]
    
    for pattern in install_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            # Extract next code block
            start = match.end()
            code_match = re.search(r"```(\w*)\n(.*?)```", content[start:], re.DOTALL)
            if code_match:
                lines.append(f"```{code_match.group(1)}")
                lines.extend(code_match.group(2).strip().split("\n")[:5])
                lines.append("```")
                break
    
    # Fallback: look for common patterns
    if not lines:
        if ecosystem == "npm":
            if "require(" in content:
                match = re.search(r"(const|var|let)\s+\w+\s*=\s*require\([^)]+\)", content)
                if match:
                    lines = ["```javascript", match.group(0), "```"]
            elif "import " in content:
                match = re.search(r"import\s+.*?from\s+['\"][^'\"]+['\"]", content)
                if match:
                    lines = ["```javascript", match.group(0), "```"]
        elif ecosystem == "py":
            if "import " in content:
                match = re.search(r"import\s+\w+", content)
                if match:
                    lines = ["```python", match.group(0), "```"]
            elif "from " in content:
                match = re.search(r"from\s+\w+\s+import\s+\w+", content)
                if match:
                    lines = ["```python", match.group(0), "```"]
    
    return lines


def _extract_top_apis(content: str) -> List[str]:
    """Extract top API methods."""
    lines = []
    
    # Look for API section
    api_patterns = [
        r"## API",
        r"## Methods",
        r"## Functions",
        r"### API",
    ]
    
    for pattern in api_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            start = match.end()
            # Extract next few method signatures
            method_matches = re.findall(
                r"^[\*\-]\s*`([^`]+)`",
                content[start:start+2000],
                re.MULTILINE
            )
            for method in method_matches[:5]:  # Top 5 methods
                lines.append(f"- `{method}`")
            break
    
    # Fallback: look for function definitions in code blocks
    if not lines:
        code_blocks = re.findall(r"```\w*\n(.*?)```", content, re.DOTALL)
        for block in code_blocks[:2]:  # Check first 2 code blocks
            # Look for function signatures
            funcs = re.findall(r"(?:function|def|const|let|var)\s+(\w+)\s*\(([^)]*)\)", block)
            for func_name, params in funcs[:5]:
                lines.append(f"- `{func_name}({params})`")
            if lines:
                break
    
    return lines


def _extract_examples(content: str) -> List[str]:
    """Extract usage examples."""
    lines = []
    
    # Look for examples section
    example_patterns = [
        r"## Example",
        r"## Usage",
        r"### Example",
        r"### Usage",
    ]
    
    for pattern in example_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            start = match.end()
            # Extract next code block
            code_match = re.search(r"```(\w*)\n(.*?)```", content[start:], re.DOTALL)
            if code_match:
                lang = code_match.group(1) or "javascript"
                code_lines = code_match.group(2).strip().split("\n")[:10]  # Max 10 lines
                lines.append(f"```{lang}")
                lines.extend(code_lines)
                lines.append("```")
                break
    
    return lines