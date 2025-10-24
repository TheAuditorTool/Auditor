"""JavaScript helper script templates for TypeScript AST extraction.

This module provides JavaScript helper scripts for extracting TypeScript/JavaScript
AST data using the TypeScript Compiler API. It operates by loading pre-extracted
JavaScript modules from the javascript/ directory and assembling them into
complete batch processing scripts.

Architecture (Phase 5 - Extraction-First):
- javascript/core_extractors.js: 18 extraction functions (imports, functions, classes, etc.)
- javascript/cfg_extractor.js: Control flow graph extraction
- javascript/batch_templates.js: ES Module and CommonJS batch scaffolding

The orchestrator (this file) loads these modules at runtime and injects them into
the batch templates via simple string concatenation (no f-string placeholders).

Workflow:
1. Python calls get_batch_helper(module_type)
2. Orchestrator reads javascript/*.js files from disk
3. Concatenates: core_extractors + cfg_extractor + batch_template
4. Returns complete JavaScript program as string
5. Python writes to temp file and executes via Node.js subprocess

This replaces the old Phase 4 architecture where all JavaScript was embedded as
Python string constants with f-string injection points.
"""

from pathlib import Path
from typing import Literal


# Module-level cache for JavaScript file contents (loaded once on first use)
_JS_CACHE = {
    'core_extractors': None,
    'cfg_extractor': None,
    'batch_es_module': None,
    'batch_commonjs': None
}


def _load_javascript_modules():
    """Load JavaScript modules from javascript/ directory into cache.

    This function is called lazily on first use of get_batch_helper().
    It loads all JavaScript files once and caches them in memory for
    subsequent calls.

    Raises:
        FileNotFoundError: If any required JavaScript module is missing
        RuntimeError: If batch_templates.js doesn't contain required separators
    """
    global _JS_CACHE

    # Get the directory containing this Python file
    current_dir = Path(__file__).parent
    js_dir = current_dir / 'javascript'

    # Verify javascript directory exists
    if not js_dir.exists():
        raise FileNotFoundError(
            f"JavaScript modules directory not found: {js_dir}\n"
            f"Expected structure:\n"
            f"  {js_dir}/core_extractors.js\n"
            f"  {js_dir}/cfg_extractor.js\n"
            f"  {js_dir}/batch_templates.js"
        )

    # Load core extractors (18 functions)
    core_path = js_dir / 'core_extractors.js'
    if not core_path.exists():
        raise FileNotFoundError(f"Missing core extractors: {core_path}")
    _JS_CACHE['core_extractors'] = core_path.read_text(encoding='utf-8')

    # Load CFG extractor
    cfg_path = js_dir / 'cfg_extractor.js'
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing CFG extractor: {cfg_path}")
    _JS_CACHE['cfg_extractor'] = cfg_path.read_text(encoding='utf-8')

    # Load and split batch templates
    batch_path = js_dir / 'batch_templates.js'
    if not batch_path.exists():
        raise FileNotFoundError(f"Missing batch templates: {batch_path}")

    batch_content = batch_path.read_text(encoding='utf-8')

    # Split on separator comments
    es_separator = '// === ES_MODULE_BATCH ==='
    cjs_separator = '// === COMMONJS_BATCH ==='

    if es_separator not in batch_content:
        raise RuntimeError(f"Batch templates missing ES Module separator: {es_separator}")
    if cjs_separator not in batch_content:
        raise RuntimeError(f"Batch templates missing CommonJS separator: {cjs_separator}")

    # Split the file into sections
    parts = batch_content.split(es_separator)
    if len(parts) != 2:
        raise RuntimeError(f"Expected exactly one {es_separator} separator, found {len(parts)-1}")

    header_section = parts[0]  # File header (not used in assembled output)
    remaining = parts[1]

    # Split ES Module and CommonJS sections
    parts = remaining.split(cjs_separator)
    if len(parts) != 2:
        raise RuntimeError(f"Expected exactly one {cjs_separator} separator, found {len(parts)-1}")

    es_template = parts[0].strip()
    cjs_template = parts[1].strip()

    _JS_CACHE['batch_es_module'] = es_template
    _JS_CACHE['batch_commonjs'] = cjs_template


def get_batch_helper(module_type: Literal["module", "commonjs"]) -> str:
    """Get the complete batch processing helper script.

    Assembles a complete JavaScript batch processing script by combining:
    1. Core extraction functions (extractImports, extractFunctions, etc.)
    2. CFG extraction function (extractCFG)
    3. Batch template scaffold (main function, error handling, etc.)

    The assembly is done via simple string concatenation - the JavaScript files
    are loaded from disk and prepended to the batch template. No f-string
    injection or placeholders are used.

    Args:
        module_type: Either "module" for ES modules or "commonjs" for CommonJS

    Returns:
        Complete JavaScript batch helper script as a string

    Raises:
        FileNotFoundError: If JavaScript modules are missing
        RuntimeError: If batch templates are malformed

    Example:
        >>> script = get_batch_helper("module")
        >>> # Write to temp file and execute
        >>> temp_path = Path(tempfile.mktemp(suffix='.mjs'))
        >>> temp_path.write_text(script)
        >>> subprocess.run(['node', str(temp_path), ...])
    """
    # Load JavaScript modules from disk (cached after first call)
    if _JS_CACHE['core_extractors'] is None:
        _load_javascript_modules()

    # Select the appropriate batch template
    if module_type == "module":
        batch_template = _JS_CACHE['batch_es_module']
    elif module_type == "commonjs":
        batch_template = _JS_CACHE['batch_commonjs']
    else:
        raise ValueError(f"Invalid module_type: {module_type}. Expected 'module' or 'commonjs'")

    # Assemble the complete script via string concatenation
    # Order: core_extractors → cfg_extractor → batch_template
    # This ensures all functions are defined before the main() function tries to call them
    assembled_script = (
        _JS_CACHE['core_extractors'] +
        '\n\n' +
        _JS_CACHE['cfg_extractor'] +
        '\n\n' +
        batch_template
    )

    return assembled_script


def get_single_file_helper(module_type: Literal["module", "commonjs"]) -> str:
    """Get the appropriate single-file helper script.

    DEPRECATED: Single-file mode is obsolete in Phase 5. Use get_batch_helper() with 1 file instead.

    Args:
        module_type: Either "module" for ES modules or "commonjs" for CommonJS

    Returns:
        Complete JavaScript helper script as a string

    Raises:
        RuntimeError: Always raises - single-file mode removed in Phase 5
    """
    raise RuntimeError(
        "Single-file mode removed in Phase 5. "
        "Single-file templates serialize full AST (512MB crash). "
        "Use get_batch_helper() with 1 file instead (sets ast: null)."
    )


__all__ = [
    'get_single_file_helper',
    'get_batch_helper',
]
