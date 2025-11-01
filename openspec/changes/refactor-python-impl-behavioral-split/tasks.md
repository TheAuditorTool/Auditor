# Implementation Tasks

## 0. Verification (MANDATORY - Complete BEFORE implementation)

- [ ] 0.1 Read entire python_impl.py (2324 lines) to understand all function dependencies
- [ ] 0.2 Read entire typescript_impl.py to understand behavioral layer patterns
- [ ] 0.3 Read entire typescript_impl_structure.py to understand structural layer patterns
- [ ] 0.4 Verify python_impl.py import usage: `grep -r "python_impl" theauditor/ --include="*.py"`
- [ ] 0.5 Confirm python/ package is active: `python -c "from theauditor.ast_extractors import python_impl; print(python_impl.__file__)"`
- [ ] 0.6 Document ALL functions in python_impl.py with classification (structural vs behavioral)
- [ ] 0.7 Identify exact split boundary (line numbers, function groups)
- [ ] 0.8 Map dependency graph: which functions call which
- [ ] 0.9 Verify NO circular dependencies will be created
- [ ] 0.10 Create verification.md with hypothesis testing results

## 1. Create python_impl_structure.py (Structural Layer)

- [ ] 1.1 Create theauditor/ast_extractors/python_impl_structure.py
- [ ] 1.2 Add module docstring following TypeScript pattern (RESPONSIBILITY, CONTRACT, CONSUMERS)
- [ ] 1.3 Copy core utility functions from python_impl.py
  - [ ] _get_type_annotation()
  - [ ] _analyze_annotation_flags()
  - [ ] _parse_function_type_comment()
  - [ ] _get_str_constant()
  - [ ] _keyword_arg()
  - [ ] _get_bool_constant()
  - [ ] _cascade_implies_delete()
  - [ ] _extract_backref_name()
  - [ ] _extract_backref_cascade()
  - [ ] _infer_relationship_type()
  - [ ] _inverse_relationship_type()
  - [ ] _is_truthy()
  - [ ] _dependency_name()
  - [ ] _extract_fastapi_dependencies()
- [ ] 1.4 Copy constants
  - [ ] SQLALCHEMY_BASE_IDENTIFIERS
  - [ ] DJANGO_MODEL_BASES
  - [ ] FASTAPI_HTTP_METHODS
- [ ] 1.5 Copy structural extractors
  - [ ] extract_python_functions()
  - [ ] extract_python_classes()
  - [ ] extract_python_imports()
  - [ ] extract_python_exports()
  - [ ] extract_python_calls()
  - [ ] extract_python_properties()
  - [ ] extract_python_attribute_annotations()
  - [ ] extract_python_function_params()
- [ ] 1.6 Copy framework extractors (stateless parts)
  - [ ] extract_sqlalchemy_definitions()
  - [ ] extract_django_definitions()
  - [ ] extract_pydantic_validators()
  - [ ] extract_flask_blueprints()
  - [ ] extract_marshmallow_schemas()
  - [ ] extract_marshmallow_fields()
  - [ ] extract_wtforms_forms()
  - [ ] extract_wtforms_fields()
  - [ ] extract_celery_tasks()
  - [ ] extract_celery_task_calls()
  - [ ] extract_celery_beat_schedules()
  - [ ] extract_pytest_fixtures()
  - [ ] extract_pytest_parametrize()
  - [ ] extract_pytest_markers()
- [ ] 1.7 Verify NO imports from python_impl.py (must be self-contained)
- [ ] 1.8 Add ARCHITECTURAL CONTRACT comment block

## 2. Refactor python_impl.py (Behavioral Layer)

- [ ] 2.1 Update module docstring to match typescript_impl.py pattern
  - [ ] Add "This module is Part 2 of the Python implementation layer split"
  - [ ] Add RESPONSIBILITY section (Behavioral Analysis)
  - [ ] Add DEPENDENCIES section (lists imports from python_impl_structure.py)
  - [ ] Add CONSUMERS section
- [ ] 2.2 Add imports from python_impl_structure.py at top
  - [ ] Import all utility functions
  - [ ] Import all constants
  - [ ] Import all structural extractors (for re-export)
- [ ] 2.3 Keep behavioral extractors in python_impl.py
  - [ ] extract_python_assignments() (uses find_containing_function_python)
  - [ ] extract_python_calls_with_args() (needs function ranges)
  - [ ] extract_python_returns() (uses find_containing_function_python)
  - [ ] extract_python_dicts() (uses function ranges for scope detection)
  - [ ] extract_python_cfg() (complex stateful CFG construction)
  - [ ] build_python_function_cfg() (CFG builder)
  - [ ] process_python_statement() (CFG processor)
- [ ] 2.4 Add re-exports from python_impl_structure.py
  - [ ] Re-export all structural extractors for backward compatibility
  - [ ] Re-export all constants
  - [ ] Re-export all utility functions
- [ ] 2.5 Update DEPRECATION NOTICE
  - [ ] Note: "Now split into python_impl.py (behavioral) + python_impl_structure.py (structural)"
  - [ ] Update module locations in deprecation notice
- [ ] 2.6 Verify import chain works: behavioral → structural (one-way dependency)

## 3. Testing & Verification

- [ ] 3.1 Run static analysis: `python -m py_compile theauditor/ast_extractors/python_impl.py`
- [ ] 3.2 Run static analysis: `python -m py_compile theauditor/ast_extractors/python_impl_structure.py`
- [ ] 3.3 Test imports work: `python -c "from theauditor.ast_extractors import python_impl; print(dir(python_impl))"`
- [ ] 3.4 Verify re-exports: `python -c "from theauditor.ast_extractors.python_impl import extract_python_functions; print(extract_python_functions)"`
- [ ] 3.5 Run unit tests (if any exist for python_impl.py)
- [ ] 3.6 Verify line counts match split: ~1150 structure + ~1174 behavioral = 2324 total
- [ ] 3.7 Verify NO duplicate function definitions across both files
- [ ] 3.8 Verify dependency direction: python_impl.py → python_impl_structure.py (never reverse)
- [ ] 3.9 Create side-by-side comparison with TypeScript split
  - [ ] typescript_impl.py (1328) vs python_impl.py (~1174)
  - [ ] typescript_impl_structure.py (1031) vs python_impl_structure.py (~1150)
- [ ] 3.10 Update verification.md with test results

## 4. Documentation

- [ ] 4.1 Add inline comments documenting layer separation
- [ ] 4.2 Update python_impl.py docstring with architecture diagram
- [ ] 4.3 Add "See Also" references between files
- [ ] 4.4 Document import patterns for future maintainers
- [ ] 4.5 Add examples of structural vs behavioral extraction
- [ ] 4.6 Update CLAUDE.md if pattern is referenced there
- [ ] 4.7 Create verification.md if not exists, document all tests performed

## 5. Final Verification

- [ ] 5.1 Re-read both files in their entirety (post-implementation audit per teamsop.md)
- [ ] 5.2 Verify NO syntax errors: `python -m py_compile theauditor/ast_extractors/python_impl*.py`
- [ ] 5.3 Verify NO circular imports
- [ ] 5.4 Verify backward compatibility maintained
- [ ] 5.5 Verify split ratio approximately 50/50 (±5%)
- [ ] 5.6 Verify pattern matches TypeScript implementation
- [ ] 5.7 Document discrepancies found during implementation
- [ ] 5.8 Mark all tasks complete only after full verification
