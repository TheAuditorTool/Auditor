# Tasks: FCE Modular Consensus Engine Refactor

## 1. Foundation
- [ ] 1.1 Create `theauditor/fce/` package directory structure
- [ ] 1.2 Create `schema.py` with Pydantic models (Fact, ConvergencePoint, AIContextBundle, etc.)
- [ ] 1.3 Write unit tests for schema validation

## 2. Collectors
- [ ] 2.1 Create `collectors/base.py` with abstract BaseCollector class
- [ ] 2.2 Port `load_graph_data_from_db` -> `collectors/graph.py`
- [ ] 2.3 Port `load_cfg_data_from_db` -> `collectors/cfg.py`
- [ ] 2.4 Port `load_taint_data_from_db` -> `collectors/taint.py`
- [ ] 2.5 Port `load_workflow_data_from_db` -> `collectors/workflow.py`
- [ ] 2.6 Port `load_graphql_findings_from_db` -> `collectors/graphql.py`
- [ ] 2.7 Port `scan_all_findings` -> `collectors/findings.py`
- [ ] 2.8 Create `collectors/churn.py` stub (currently empty dict in fce.py)
- [ ] 2.9 Create `collectors/coverage.py` stub (currently empty dict in fce.py)
- [ ] 2.10 Write unit tests for each collector

## 3. Analyzers
- [ ] 3.1 Create `analyzers/convergence.py` with Signal Density algorithm
- [ ] 3.2 Port path correlation from `PathCorrelator` integration
- [ ] 3.3 Remove ALL hardcoded thresholds (complexity <= 20, coverage >= 50, etc.)
- [ ] 3.4 Implement fact stacking (NOT risk scoring)
- [ ] 3.5 Write unit tests for convergence logic

## 4. Engine Orchestration
- [ ] 4.1 Create `engine.py` as the main orchestrator
- [ ] 4.2 Wire collectors to feed into analyzers
- [ ] 4.3 Implement output JSON writer with new schema
- [ ] 4.4 Create `resolver.py` for AI Context Bundle generation

## 5. Integration
- [ ] 5.1 Update `theauditor/commands/fce.py` to import from `theauditor.fce.engine`
- [ ] 5.2 Update `theauditor/fce/__init__.py` to export public API
- [ ] 5.3 Archive old `theauditor/fce.py` (move to `_fce_legacy.py` or delete)
- [ ] 5.4 Run full test suite to verify integration

## 6. Cleanup Legacy
- [ ] 6.1 Delete hardcoded "meta finding" types (ARCHITECTURAL_RISK_ESCALATION, etc.)
- [ ] 6.2 Delete `register_meta` function and meta_registry
- [ ] 6.3 Delete all severity elevation logic
- [ ] 6.4 Delete subprocess tool running (pytest/npm) - move to separate command if needed

## 7. Documentation
- [ ] 7.1 Update command docstring in `commands/fce.py`
- [ ] 7.2 Document new output format schema
- [ ] 7.3 Add migration notes for users of old format
