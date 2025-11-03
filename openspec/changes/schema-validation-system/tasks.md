# Implementation Tasks

**Change ID**: `schema-validation-system`
**Total Time**: 70 minutes

## 0. Verification ✅ COMPLETE
- [x] 0.1 Read teamsop.md and AGENTS.md
- [x] 0.2 Test 8 hypotheses about codebase
- [x] 0.3 Document findings in verification.md

## 1. Immediate Fix (5 min) - P0
- [ ] 1.1 Run codegen to fix 29 missing classes
- [ ] 1.2 Verify 154 accessor classes exist
- [ ] 1.3 Test imports work

## 2. Create Validator (20 min) - P1
- [ ] 2.1 Create validator.py with SchemaValidator class
- [ ] 2.2 Implement compute_schema_hash() (SHA-256)
- [ ] 2.3 Implement validate() method
- [ ] 2.4 Implement regenerate() method
- [ ] 2.5 Add dev/prod mode detection

## 3. Add CLI Commands (15 min) - P2
- [ ] 3.1 Create commands/schema.py
- [ ] 3.2 Implement aud schema --check
- [ ] 3.3 Implement aud schema --regen
- [ ] 3.4 Register in cli.py

## 4. Add Import Hook (10 min) - P2
- [ ] 4.1 Modify schemas/__init__.py
- [ ] 4.2 Add import-time validation
- [ ] 4.3 Add THEAUDITOR_NO_VALIDATION bypass

## 5. Create Tests (15 min) - P3
- [ ] 5.1 Create test_schema_integrity.py
- [ ] 5.2 Test hash validation
- [ ] 5.3 Test file existence
- [ ] 5.4 Run test suite

## 6. Documentation (5 min) - P3
- [ ] 6.1 Update codegen.py to write hash
- [ ] 6.2 Add .schema_hash to .gitignore
- [ ] 6.3 Update CLAUDE.md

## 7. Post-Implementation Audit
- [ ] 7.1 Re-read all modified files
- [ ] 7.2 Run full test suite
- [ ] 7.3 Test dev and prod modes
- [ ] 7.4 Complete audit report (Template C-4.20)
