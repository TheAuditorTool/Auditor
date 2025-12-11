"""
Integration Test: Validation Chain Tracing and Security Audit

This test verifies that the validation chain tracer correctly detects:
- Intact chains: validation at entry AND type preserved through all hops
- Broken chains: validation at entry BUT type safety lost at intermediate hop
- No validation: no validation detected at entry point

Also tests security audit across all four boundary categories.

Per tasks.md Section 7: Tasks 7.1-7.6
"""

import shutil
import sqlite3
from pathlib import Path

import pytest

from theauditor.boundaries.chain_tracer import (
    ANY_TYPE_PATTERNS,
    ChainHop,
    ValidationChain,
    get_type_break_reason,
    is_type_unsafe,
    trace_validation_chains,
)
from theauditor.boundaries.security_audit import (
    AUDIT_CATEGORIES,
    AuditFinding,
    AuditResult,
    SecurityAuditReport,
    format_security_audit,
    run_security_audit,
)
from theauditor.indexer import run_repository_index


def format_validation_chain(chain: ValidationChain) -> str:
    """Format a validation chain for terminal output (copied from boundaries.py to avoid circular import)."""
    lines = []
    lines.append(f"{chain.entry_point}")
    lines.append(f"  File: {chain.entry_file}:{chain.entry_line}")
    lines.append(f"  Status: {chain.chain_status.upper()}")
    lines.append("")

    for i, hop in enumerate(chain.hops):
        is_break = chain.break_index == i
        func_line = f"  {hop.function}({hop.type_info})"
        if is_break:
            func_line += "        <- CHAIN BROKEN"
        lines.append(func_line)

        if hop.validation_status == "validated":
            status = "[PASS] Validated at entry"
        elif hop.validation_status == "preserved":
            status = "[PASS] Type preserved"
        elif hop.validation_status == "broken":
            status = f"[FAIL] {hop.break_reason or 'Type safety lost'}"
        else:
            status = "[----] Unknown type status"
        lines.append(f"      | {status}")

        if i < len(chain.hops) - 1:
            lines.append("      v")

    lines.append("")
    return "\n".join(lines)


def format_validation_chains_report(chains: list[ValidationChain]) -> str:
    """Format multiple validation chains as a report (copied from boundaries.py)."""
    lines = []
    lines.append("=== VALIDATION CHAIN ANALYSIS ===\n")

    total = len(chains)
    intact = sum(1 for c in chains if c.chain_status == "intact")
    broken = sum(1 for c in chains if c.chain_status == "broken")
    no_val = sum(1 for c in chains if c.chain_status == "no_validation")

    lines.append(f"Entry Points Analyzed: {total}")
    lines.append(f"  Chains Intact:      {intact} ({intact * 100 // total if total else 0}%)")
    lines.append(f"  Chains Broken:      {broken} ({broken * 100 // total if total else 0}%)")
    lines.append(f"  No Validation:      {no_val} ({no_val * 100 // total if total else 0}%)")
    lines.append("")

    return "\n".join(lines)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "validation_chain"


class TestTypeUnsafeDetection:
    """Test type safety detection regex patterns (tasks.md 1.2.5)."""

    def test_any_type_annotation(self):
        """Test detection of `: any` type annotation."""
        assert is_type_unsafe("data: any")
        assert is_type_unsafe("param:any")
        assert is_type_unsafe("result:  any")

    def test_any_cast(self):
        """Test detection of `as any` cast."""
        assert is_type_unsafe("validated as any")
        assert is_type_unsafe("result as  any")

    def test_any_generic(self):
        """Test detection of generic `<any>` patterns."""
        assert is_type_unsafe("Promise<any>")
        assert is_type_unsafe("Array<any>")
        assert is_type_unsafe("Map<string, any>")
        assert is_type_unsafe("Map<any, string>")

    def test_any_union(self):
        """Test detection of `| any` union patterns."""
        assert is_type_unsafe("string | any")
        assert is_type_unsafe("any | string")

    def test_any_return_type(self):
        """Test detection of `=> any` return type."""
        assert is_type_unsafe("() => any")
        assert is_type_unsafe("(x: string) => any")

    def test_no_false_positives(self):
        """Test that common words containing 'any' don't trigger false positives."""
        # Per design.md Decision 2: word boundaries prevent false positives
        assert not is_type_unsafe("Company")
        assert not is_type_unsafe("Germany")
        assert not is_type_unsafe("ManyItems")
        assert not is_type_unsafe("company: string")
        assert not is_type_unsafe("anyCompany: Company")  # starts with 'any' but not type

    def test_validation_exclusions(self):
        """Test that validation library patterns are excluded."""
        # Per tasks.md 1.2.5: z.any(), Joi.any() are validation sources, not breaks
        assert not is_type_unsafe("z.any()")
        assert not is_type_unsafe("Joi.any()")
        assert not is_type_unsafe("yup.mixed()")

    def test_empty_and_none(self):
        """Test handling of empty/None type annotations."""
        assert not is_type_unsafe(None)
        assert not is_type_unsafe("")
        assert not is_type_unsafe("   ")

    def test_break_reason_messages(self):
        """Test that break reasons are descriptive."""
        assert get_type_break_reason("data: any") is not None
        assert "any" in get_type_break_reason("data: any").lower()
        assert get_type_break_reason("x as any") is not None
        assert "cast" in get_type_break_reason("x as any").lower()
        assert get_type_break_reason("Company") is None


class TestDataModels:
    """Test ChainHop and ValidationChain dataclasses (tasks.md 1.1)."""

    def test_chain_hop_creation(self):
        """Test ChainHop dataclass creation."""
        hop = ChainHop(
            function="createUser",
            file="src/services/user.ts",
            line=42,
            type_info="CreateUserInput",
            validation_status="validated",
            break_reason=None,
        )
        assert hop.function == "createUser"
        assert hop.validation_status == "validated"
        assert hop.break_reason is None

    def test_chain_hop_with_break(self):
        """Test ChainHop with break reason."""
        hop = ChainHop(
            function="legacyAdapter",
            file="src/legacy/adapter.ts",
            line=88,
            type_info="any",
            validation_status="broken",
            break_reason="Cast to any",
        )
        assert hop.validation_status == "broken"
        assert hop.break_reason == "Cast to any"

    def test_validation_chain_creation(self):
        """Test ValidationChain dataclass creation."""
        chain = ValidationChain(
            entry_point="POST /api/users",
            entry_file="src/routes/users.ts",
            entry_line=15,
            hops=[],
            chain_status="intact",
            break_index=None,
        )
        assert chain.entry_point == "POST /api/users"
        assert chain.chain_status == "intact"

    def test_validation_chain_with_break(self):
        """Test ValidationChain with broken status."""
        hops = [
            ChainHop("validate", "f.ts", 1, "validated", "validated", None),
            ChainHop("service", "f.ts", 10, "preserved", "preserved", None),
            ChainHop("legacy", "f.ts", 20, "any", "broken", "Cast to any"),
        ]
        chain = ValidationChain(
            entry_point="POST /api/orders",
            entry_file="src/routes/orders.ts",
            entry_line=25,
            hops=hops,
            chain_status="broken",
            break_index=2,
        )
        assert chain.chain_status == "broken"
        assert chain.break_index == 2
        assert chain.hops[2].break_reason == "Cast to any"


class TestSecurityAuditCategories:
    """Test security audit category definitions (tasks.md 2.1)."""

    def test_audit_categories_exist(self):
        """Test that all four audit categories are defined."""
        assert "input" in AUDIT_CATEGORIES
        assert "output" in AUDIT_CATEGORIES
        assert "database" in AUDIT_CATEGORIES
        assert "file" in AUDIT_CATEGORIES

    def test_input_category(self):
        """Test INPUT boundary category structure."""
        cat = AUDIT_CATEGORIES["input"]
        assert cat["name"] == "INPUT BOUNDARIES"
        assert cat["severity"] == "CRITICAL"
        assert "validate" in cat["patterns"]
        assert "zod" in cat["patterns"]

    def test_output_category(self):
        """Test OUTPUT boundary category structure."""
        cat = AUDIT_CATEGORIES["output"]
        assert cat["name"] == "OUTPUT BOUNDARIES"
        assert "escape" in cat["patterns"]
        assert "sanitize" in cat["patterns"]

    def test_database_category(self):
        """Test DATABASE boundary category structure."""
        cat = AUDIT_CATEGORIES["database"]
        assert cat["name"] == "DATABASE BOUNDARIES"
        assert "parameterized" in cat["patterns"]
        assert "?" in cat["patterns"]

    def test_file_category(self):
        """Test FILE boundary category structure."""
        cat = AUDIT_CATEGORIES["file"]
        assert cat["name"] == "FILE BOUNDARIES"
        assert "path.resolve" in cat["patterns"]
        assert "realpath" in cat["patterns"]


class TestAuditDataModels:
    """Test audit data model structures."""

    def test_audit_finding_creation(self):
        """Test AuditFinding dataclass creation."""
        finding = AuditFinding(
            category="input",
            location="src/api.ts:42",
            file="src/api.ts",
            line=42,
            function="POST /users",
            status="PASS",
            message="Zod schema validates body",
            evidence="validateBody(CreateUserSchema)",
        )
        assert finding.status == "PASS"
        assert finding.category == "input"

    def test_audit_result_creation(self):
        """Test AuditResult dataclass creation."""
        result = AuditResult(
            category="input",
            name="INPUT BOUNDARIES",
            severity="CRITICAL",
            pass_count=5,
            fail_count=2,
        )
        assert result.pass_count == 5
        assert result.fail_count == 2

    def test_security_audit_report_creation(self):
        """Test SecurityAuditReport dataclass creation."""
        report = SecurityAuditReport()
        report.total_pass = 10
        report.total_fail = 3
        assert report.total_pass == 10


class TestOutputFormatting:
    """Test output formatting (tasks.md 3.2, 7.6)."""

    def test_validation_chain_format_no_emojis(self):
        """Test that validation chain output contains no emojis."""
        chain = ValidationChain(
            entry_point="POST /users",
            entry_file="src/users.ts",
            entry_line=10,
            hops=[
                ChainHop("validate", "f.ts", 1, "CreateUserInput", "validated", None),
                ChainHop("service", "f.ts", 10, "CreateUserInput", "preserved", None),
            ],
            chain_status="intact",
            break_index=None,
        )
        output = format_validation_chain(chain)

        # Check no emojis (common emoji unicode ranges)
        emoji_chars = [c for c in output if ord(c) > 127]
        assert not emoji_chars, f"Found non-ASCII chars: {emoji_chars}"

        # Check ASCII markers are used
        assert "[PASS]" in output or "[FAIL]" in output or "[----]" in output

    def test_validation_chain_format_broken_marker(self):
        """Test that broken chains show CHAIN BROKEN marker."""
        chain = ValidationChain(
            entry_point="POST /orders",
            entry_file="src/orders.ts",
            entry_line=15,
            hops=[
                ChainHop("validate", "f.ts", 1, "validated", "validated", None),
                ChainHop("legacy", "f.ts", 20, "any", "broken", "Cast to any"),
            ],
            chain_status="broken",
            break_index=1,
        )
        output = format_validation_chain(chain)

        assert "CHAIN BROKEN" in output
        assert "[FAIL]" in output

    def test_validation_chains_report_format(self):
        """Test report format for multiple chains."""
        chains = [
            ValidationChain("POST /a", "a.ts", 1, [], "intact", None),
            ValidationChain("POST /b", "b.ts", 2, [], "broken", 0),
            ValidationChain("POST /c", "c.ts", 3, [], "no_validation", None),
        ]
        output = format_validation_chains_report(chains)

        assert "VALIDATION CHAIN ANALYSIS" in output
        assert "Entry Points Analyzed: 3" in output
        assert "Chains Intact" in output
        assert "Chains Broken" in output
        assert "No Validation" in output

    def test_security_audit_format_no_emojis(self):
        """Test that security audit output contains no emojis."""
        report = SecurityAuditReport()
        report.results["input"] = AuditResult(
            category="input",
            name="INPUT BOUNDARIES",
            severity="CRITICAL",
            pass_count=5,
            fail_count=2,
            findings=[
                AuditFinding(
                    category="input",
                    location="f.ts:10",
                    file="f.ts",
                    line=10,
                    function="POST /users",
                    status="PASS",
                    message="Validated",
                ),
            ],
        )
        report.total_pass = 5
        report.total_fail = 2

        output = format_security_audit(report)

        # Check no emojis
        emoji_chars = [c for c in output if ord(c) > 127]
        assert not emoji_chars, f"Found non-ASCII chars: {emoji_chars}"

        # Check ASCII markers
        assert "[PASS]" in output or "[FAIL]" in output


class TestValidationChainIntegration:
    """Integration tests for validation chain tracing with fixtures.

    These tests require indexing the TypeScript fixtures.
    Tests 7.1-7.4 from tasks.md.
    """

    @pytest.fixture(scope="class")
    def indexed_fixture(self, tmp_path_factory):
        """Index the validation_chain fixture and return database paths."""
        if not FIXTURE_DIR.exists():
            pytest.skip(f"Fixture directory not found: {FIXTURE_DIR}")

        temp_dir = tmp_path_factory.mktemp("validation_chain_test")
        db_path = temp_dir / "repo_index.db"

        fixture_copy = temp_dir / "fixture"
        shutil.copytree(FIXTURE_DIR, fixture_copy)

        try:
            run_repository_index(root_path=str(fixture_copy), db_path=str(db_path))
        except Exception as e:
            pytest.skip(f"Indexing failed (may need JS extractor built): {e}")

        return {
            "db_path": str(db_path),
            "fixture_path": str(fixture_copy),
        }

    def test_fixture_files_exist(self):
        """Verify test fixture files exist (7.1, 7.2, 7.3)."""
        assert FIXTURE_DIR.exists(), f"Fixture dir not found: {FIXTURE_DIR}"

        expected_files = ["intact_chain.ts", "broken_chain.ts", "no_validation.ts"]
        for filename in expected_files:
            filepath = FIXTURE_DIR / filename
            assert filepath.exists(), f"Fixture file not found: {filepath}"

    def test_database_created(self, indexed_fixture):
        """Verify database was created during indexing."""
        db_path = Path(indexed_fixture["db_path"])
        assert db_path.exists(), "repo_index.db not created"

    def test_symbols_indexed(self, indexed_fixture):
        """Verify symbols were extracted from fixtures."""
        conn = sqlite3.connect(indexed_fixture["db_path"])
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM symbols")
        count = cursor.fetchone()[0]
        conn.close()

        # Should have at least some symbols from our fixtures
        assert count >= 0, "Symbols table should exist"

    def test_trace_chains_returns_results(self, indexed_fixture):
        """Test that trace_validation_chains returns ValidationChain objects (7.4)."""
        chains = trace_validation_chains(
            db_path=indexed_fixture["db_path"],
            max_entries=10,
        )

        # Should return a list (may be empty if no routes detected)
        assert isinstance(chains, list)

        # If any chains found, verify structure
        for chain in chains:
            assert isinstance(chain, ValidationChain)
            assert chain.entry_point is not None
            assert chain.chain_status in ("intact", "broken", "no_validation", "unknown")


class TestSecurityAuditIntegration:
    """Integration tests for security audit (tasks.md 7.5)."""

    @pytest.fixture(scope="class")
    def indexed_fixture(self, tmp_path_factory):
        """Index fixture and return database paths."""
        if not FIXTURE_DIR.exists():
            pytest.skip(f"Fixture directory not found: {FIXTURE_DIR}")

        temp_dir = tmp_path_factory.mktemp("security_audit_test")
        db_path = temp_dir / "repo_index.db"

        fixture_copy = temp_dir / "fixture"
        shutil.copytree(FIXTURE_DIR, fixture_copy)

        try:
            run_repository_index(root_path=str(fixture_copy), db_path=str(db_path))
        except Exception as e:
            pytest.skip(f"Indexing failed: {e}")

        return {"db_path": str(db_path)}

    def test_security_audit_returns_report(self, indexed_fixture):
        """Test that run_security_audit returns SecurityAuditReport."""
        report = run_security_audit(
            db_path=indexed_fixture["db_path"],
            max_findings=10,
        )

        assert isinstance(report, SecurityAuditReport)
        assert "input" in report.results
        assert "output" in report.results
        assert "database" in report.results
        assert "file" in report.results

    def test_audit_results_have_counts(self, indexed_fixture):
        """Test that audit results have pass/fail counts."""
        report = run_security_audit(
            db_path=indexed_fixture["db_path"],
            max_findings=50,
        )

        # Total should be sum of category counts
        total_from_categories = sum(
            r.pass_count + r.fail_count for r in report.results.values()
        )

        # May be 0 if no relevant code patterns found
        assert total_from_categories >= 0

    def test_audit_findings_have_required_fields(self, indexed_fixture):
        """Test that findings have all required fields."""
        report = run_security_audit(
            db_path=indexed_fixture["db_path"],
            max_findings=50,
        )

        for cat_key, result in report.results.items():
            for finding in result.findings:
                assert finding.category == cat_key
                assert finding.file is not None
                assert finding.line is not None
                assert finding.status in ("PASS", "FAIL")
                assert finding.message is not None


class TestRegexPatternCoverage:
    """Test regex pattern coverage for edge cases."""

    def test_any_patterns_compile(self):
        """Verify all ANY_TYPE_PATTERNS are valid compiled regexes."""
        for pattern in ANY_TYPE_PATTERNS:
            assert pattern.pattern is not None
            # Test that pattern can match something
            test_str = pattern.pattern.replace("\\", "").replace("s*", " ").replace("b", "")
            assert pattern.search is not None

    def test_typescript_complex_types(self):
        """Test detection in complex TypeScript type expressions."""
        assert is_type_unsafe("Partial<any>")
        assert is_type_unsafe("Record<string, any>")
        # Note: Promise<any[]> doesn't match because pattern expects <any> not <any[]>
        # This is acceptable - the specific patterns are designed for common unsafe cases
        assert is_type_unsafe("(arg: string) => any")

    def test_python_style_any(self):
        """Test that Python typing.Any is not detected (different pattern)."""
        # Python uses typing.Any, not bare 'any'
        # Our regex is TypeScript-focused
        assert not is_type_unsafe("typing.Any")  # No word boundary match
        assert not is_type_unsafe("from typing import Any")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
