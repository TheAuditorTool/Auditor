"""JavaScript helper script templates for TypeScript AST extraction.

This module provides JavaScript helper scripts for extracting TypeScript/JavaScript
AST data using the TypeScript Compiler API. It operates by loading pre-extracted
JavaScript modules from the javascript/ directory and assembling them into
complete batch processing scripts.

Architecture (Phase 5 - Extraction-First, Domain-Separated):
- javascript/core_language.js: Language structure extractors (functions, classes, scope)
- javascript/data_flow.js: Data flow extractors (assignments, calls, returns, taint)
- javascript/module_framework.js: Module/framework extractors (imports, env vars, ORM)
- javascript/security_extractors.js: Security pattern detection (ORM, API endpoints, etc.)
- javascript/framework_extractors.js: Framework patterns (React components, hooks, Vue)
- javascript/sequelize_extractors.js: Sequelize ORM model extraction
- javascript/bullmq_extractors.js: BullMQ job queue extraction
- javascript/angular_extractors.js: Angular framework extraction
- javascript/cfg_extractor.js: Control flow graph extraction
- javascript/batch_templates.js: ES Module and CommonJS batch scaffolding

The orchestrator (this file) loads these modules at runtime and injects them into
the batch templates via simple string concatenation (no f-string placeholders).

Workflow:
1. Python calls get_batch_helper(module_type)
2. Orchestrator reads javascript/*.js files from disk
3. Concatenates: core → security → framework → sequelize → bullmq → angular → cfg → batch_template
4. Returns complete JavaScript program as string
5. Python writes to temp file and executes via Node.js subprocess

This replaces the old Phase 4 architecture where all JavaScript was embedded as
Python string constants with f-string injection points.
"""

from pathlib import Path
from typing import Literal


# Module-level cache for JavaScript file contents (loaded once on first use)
_JS_CACHE = {
    'core_language': None,
    'data_flow': None,
    'module_framework': None,
    'security_extractors': None,
    'framework_extractors': None,
    'sequelize_extractors': None,
    'bullmq_extractors': None,
    'angular_extractors': None,
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
            f"  {js_dir}/core_ast_extractors.js\n"
            f"  {js_dir}/security_extractors.js\n"
            f"  {js_dir}/framework_extractors.js\n"
            f"  {js_dir}/cfg_extractor.js\n"
            f"  {js_dir}/batch_templates.js"
        )

    # Load core language extractors (language structure layer)
    core_lang_path = js_dir / 'core_language.js'
    if not core_lang_path.exists():
        raise FileNotFoundError(f"Missing core language extractors: {core_lang_path}")
    _JS_CACHE['core_language'] = core_lang_path.read_text(encoding='utf-8')

    # Load data flow extractors (data flow & taint layer)
    data_flow_path = js_dir / 'data_flow.js'
    if not data_flow_path.exists():
        raise FileNotFoundError(f"Missing data flow extractors: {data_flow_path}")
    _JS_CACHE['data_flow'] = data_flow_path.read_text(encoding='utf-8')

    # Load module/framework extractors (integration layer)
    module_fw_path = js_dir / 'module_framework.js'
    if not module_fw_path.exists():
        raise FileNotFoundError(f"Missing module/framework extractors: {module_fw_path}")
    _JS_CACHE['module_framework'] = module_fw_path.read_text(encoding='utf-8')

    # Load security extractors (SAST patterns)
    security_path = js_dir / 'security_extractors.js'
    if not security_path.exists():
        raise FileNotFoundError(f"Missing security extractors: {security_path}")
    _JS_CACHE['security_extractors'] = security_path.read_text(encoding='utf-8')

    # Load framework extractors (React, Vue, TypeScript, etc.)
    framework_path = js_dir / 'framework_extractors.js'
    if not framework_path.exists():
        raise FileNotFoundError(f"Missing framework extractors: {framework_path}")
    _JS_CACHE['framework_extractors'] = framework_path.read_text(encoding='utf-8')

    # Load Sequelize ORM extractors
    sequelize_path = js_dir / 'sequelize_extractors.js'
    if not sequelize_path.exists():
        raise FileNotFoundError(f"Missing Sequelize extractors: {sequelize_path}")
    _JS_CACHE['sequelize_extractors'] = sequelize_path.read_text(encoding='utf-8')

    # Load BullMQ job queue extractors
    bullmq_path = js_dir / 'bullmq_extractors.js'
    if not bullmq_path.exists():
        raise FileNotFoundError(f"Missing BullMQ extractors: {bullmq_path}")
    _JS_CACHE['bullmq_extractors'] = bullmq_path.read_text(encoding='utf-8')

    # Load Angular framework extractors
    angular_path = js_dir / 'angular_extractors.js'
    if not angular_path.exists():
        raise FileNotFoundError(f"Missing Angular extractors: {angular_path}")
    _JS_CACHE['angular_extractors'] = angular_path.read_text(encoding='utf-8')

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
    1. Core AST extractors (foundation - imports, functions, classes, etc.)
    2. Security extractors (SAST patterns - ORM queries, API endpoints, etc.)
    3. Framework extractors (React components, hooks, Vue)
    4. Sequelize extractors (ORM models and relationships)
    5. BullMQ extractors (job queues and workers)
    6. Angular extractors (components, services, modules)
    7. CFG extraction function (extractCFG)
    8. Batch template scaffold (main function, error handling, etc.)

    The assembly is done via simple string concatenation - the JavaScript files
    are loaded from disk and prepended to the batch template. No f-string
    injection or placeholders are used.

    Assembly order is important:
    - Core must come first (foundation layer)
    - Security/Framework depend on core extractors
    - Sequelize/BullMQ/Angular depend on core extractors
    - CFG extraction is independent
    - Batch template orchestrates everything

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
    if _JS_CACHE['core_language'] is None:
        _load_javascript_modules()

    # Select the appropriate batch template
    if module_type == "module":
        batch_template = _JS_CACHE['batch_es_module']
    elif module_type == "commonjs":
        batch_template = _JS_CACHE['batch_commonjs']
    else:
        raise ValueError(f"Invalid module_type: {module_type}. Expected 'module' or 'commonjs'")

    # Assemble the complete script via string concatenation
    # Order: core → security → framework → sequelize → bullmq → angular → cfg → batch_template
    # This ensures all functions are defined before the main() function tries to call them
    assembled_script = (
        _JS_CACHE['core_language'] +
        '\n\n' +
        _JS_CACHE['data_flow'] +
        '\n\n' +
        _JS_CACHE['module_framework'] +
        '\n\n' +
        _JS_CACHE['security_extractors'] +
        '\n\n' +
        _JS_CACHE['framework_extractors'] +
        '\n\n' +
        _JS_CACHE['sequelize_extractors'] +
        '\n\n' +
        _JS_CACHE['bullmq_extractors'] +
        '\n\n' +
        _JS_CACHE['angular_extractors'] +
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
