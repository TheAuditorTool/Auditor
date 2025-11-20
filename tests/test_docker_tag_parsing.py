"""Unit tests for Docker tag semantic parsing and version comparison."""

import pytest
from theauditor.deps import _parse_docker_tag, _extract_base_preference, _is_prerelease_version


class TestDockerTagParsing:
    """Test Docker tag semantic version parsing."""

    def test_parse_simple_major_version(self):
        """Test parsing tags with only major version."""
        result = _parse_docker_tag("17")
        assert result is not None
        assert result['version'] == (17, 0, 0)
        assert result['stability'] == 'stable'
        assert result['variant'] == ''

    def test_parse_major_minor_version(self):
        """Test parsing tags with major.minor version."""
        result = _parse_docker_tag("17.2")
        assert result is not None
        assert result['version'] == (17, 2, 0)
        assert result['stability'] == 'stable'

    def test_parse_full_semantic_version(self):
        """Test parsing tags with major.minor.patch."""
        result = _parse_docker_tag("17.2.1")
        assert result is not None
        assert result['version'] == (17, 2, 1)
        assert result['stability'] == 'stable'

    def test_parse_with_alpine_variant(self):
        """Test that alpine variant doesn't trigger alpha detection."""
        result = _parse_docker_tag("17-alpine3.21")
        assert result is not None
        assert result['version'] == (17, 0, 0)
        assert result['stability'] == 'stable'  # NOT alpha!
        assert result['variant'] == 'alpine3.21'

    def test_parse_with_slim_variant(self):
        """Test slim variant parsing."""
        result = _parse_docker_tag("3.11-slim")
        assert result is not None
        assert result['version'] == (3, 11, 0)
        assert result['stability'] == 'stable'
        assert result['variant'] == 'slim'

    def test_parse_with_bookworm_variant(self):
        """Test that bookworm doesn't trigger beta detection."""
        result = _parse_docker_tag("15.15-bookworm")
        assert result is not None
        assert result['version'] == (15, 15, 0)
        assert result['stability'] == 'stable'  # NOT beta!
        assert result['variant'] == 'bookworm'


class TestStabilityDetection:
    """Test pre-release stability detection."""

    def test_detect_alpha_version(self):
        """Test alpha version detection."""
        result = _parse_docker_tag("3.15.0a1")
        assert result is not None
        assert result['stability'] == 'alpha'
        assert result['variant'] == 'a1'

    def test_detect_alpha_with_variant(self):
        """Test alpha detection with additional variant."""
        result = _parse_docker_tag("3.15.0a1-windowsservercore")
        assert result is not None
        assert result['stability'] == 'alpha'

    def test_detect_beta_version(self):
        """Test beta version detection."""
        result = _parse_docker_tag("3.14b2-slim")
        assert result is not None
        assert result['stability'] == 'beta'

    def test_detect_rc_version(self):
        """Test release candidate detection."""
        result = _parse_docker_tag("8.4-rc1")
        assert result is not None
        assert result['stability'] == 'rc'
        assert result['variant'] == 'rc1'

    def test_detect_rc_in_variant(self):
        """Test RC detection in variant portion."""
        result = _parse_docker_tag("8.4-rc1-bookworm")
        assert result is not None
        assert result['stability'] == 'rc'

    def test_detect_dev_version(self):
        """Test development version detection."""
        result = _parse_docker_tag("17-nightly")
        assert result is not None
        assert result['stability'] == 'dev'


class TestVariantExtraction:
    """Test variant string extraction."""

    def test_extract_variant_with_dash(self):
        """Test variant extraction with leading dash."""
        result = _parse_docker_tag("17-alpine")
        assert result is not None
        assert result['variant'] == 'alpine'  # Dash stripped

    def test_extract_complex_variant(self):
        """Test complex variant extraction."""
        result = _parse_docker_tag("17.7-alpine3.22")
        assert result is not None
        assert result['version'] == (17, 7, 0)
        assert result['variant'] == 'alpine3.22'

    def test_extract_management_variant(self):
        """Test management variant extraction."""
        result = _parse_docker_tag("3.13-management-alpine")
        assert result is not None
        assert result['variant'] == 'management-alpine'


class TestMetaTagRejection:
    """Test that meta tags are rejected."""

    def test_reject_latest_tag(self):
        """Test that 'latest' tag returns None."""
        result = _parse_docker_tag("latest")
        assert result is None

    def test_reject_alpine_tag(self):
        """Test that bare 'alpine' tag returns None."""
        result = _parse_docker_tag("alpine")
        assert result is None

    def test_reject_slim_tag(self):
        """Test that bare 'slim' tag returns None."""
        result = _parse_docker_tag("slim")
        assert result is None

    def test_reject_bookworm_tag(self):
        """Test that bare 'bookworm' tag returns None."""
        result = _parse_docker_tag("bookworm")
        assert result is None


class TestSemanticVersionComparison:
    """Test that version tuples sort correctly."""

    def test_version_tuple_sorting(self):
        """Test that version tuples sort in correct semantic order."""
        versions = [
            (15, 15, 0),
            (17, 7, 0),
            (14, 20, 0),
            (17, 0, 0),
            (15, 0, 0),
            (18, 1, 0),
        ]
        sorted_versions = sorted(versions, reverse=True)

        # Expected order: 18.1.0, 17.7.0, 17.0.0, 15.15.0, 15.0.0, 14.20.0
        assert sorted_versions[0] == (18, 1, 0)
        assert sorted_versions[1] == (17, 7, 0)
        assert sorted_versions[2] == (17, 0, 0)
        assert sorted_versions[3] == (15, 15, 0)


class TestBasePreferenceExtraction:
    """Test base image preference extraction."""

    def test_extract_alpine_preference(self):
        """Test alpine base preference extraction."""
        base = _extract_base_preference("17-alpine3.21")
        assert base == 'alpine'

    def test_extract_slim_preference(self):
        """Test slim base preference extraction."""
        base = _extract_base_preference("3.11-slim")
        assert base == 'slim'

    def test_extract_bookworm_preference(self):
        """Test bookworm base preference extraction."""
        base = _extract_base_preference("15.15-bookworm")
        assert base == 'bookworm'

    def test_extract_windowsservercore_preference(self):
        """Test windowsservercore base preference extraction."""
        base = _extract_base_preference("17-windowsservercore-ltsc2022")
        assert base == 'windowsservercore'

    def test_no_base_preference(self):
        """Test extraction when no recognizable base exists."""
        base = _extract_base_preference("17")
        assert base == ''


class TestPythonPreReleaseDetection:
    """Test Python package pre-release version detection."""

    def test_detect_alpha_version(self):
        """Test detection of Python alpha versions."""
        assert _is_prerelease_version("1.0a1") is True
        assert _is_prerelease_version("2.5.0a2") is True

    def test_detect_beta_version(self):
        """Test detection of Python beta versions."""
        assert _is_prerelease_version("1.0b1") is True
        assert _is_prerelease_version("2.5.0b2") is True

    def test_detect_rc_version(self):
        """Test detection of Python release candidates."""
        assert _is_prerelease_version("1.0rc1") is True
        assert _is_prerelease_version("3.0.0rc2") is True

    def test_detect_dev_version(self):
        """Test detection of Python dev versions."""
        assert _is_prerelease_version("1.0.dev0") is True
        assert _is_prerelease_version("2.5-dev") is True

    def test_stable_versions(self):
        """Test that stable versions are not flagged as pre-release."""
        assert _is_prerelease_version("1.0.0") is False
        assert _is_prerelease_version("2.5.3") is False
        assert _is_prerelease_version("10.12.99") is False


class TestProductionScenarios:
    """Test real-world production scenarios."""

    def test_postgres_17_to_18_upgrade(self):
        """Test postgres 17-alpine should upgrade to 18-alpine, not downgrade to 15."""
        current = _parse_docker_tag("17-alpine3.21")
        v15 = _parse_docker_tag("15.15-trixie")
        v18 = _parse_docker_tag("18.1-alpine3.22")

        assert current is not None
        assert v15 is not None
        assert v18 is not None

        # Verify semantic version comparison
        assert v18['version'] > current['version']
        assert current['version'] > v15['version']

        # Verify base preservation
        assert 'alpine' in current['variant']
        assert 'alpine' in v18['variant']
        assert 'alpine' not in v15['variant']

    def test_redis_rc_filtering(self):
        """Test redis should not suggest RC versions."""
        stable = _parse_docker_tag("8.2.3-alpine3.22")
        rc = _parse_docker_tag("8.4-rc1-bookworm")

        assert stable is not None
        assert rc is not None

        assert stable['stability'] == 'stable'
        assert rc['stability'] == 'rc'

    def test_python_alpine_not_available(self):
        """Test Python 3.14 with no alpine variant should not suggest slim."""
        # If 3.14-alpine doesn't exist but 3.14-slim does,
        # we should NOT suggest upgrading 3.12-alpine to 3.14-slim
        current = _parse_docker_tag("3.12-alpine3.21")
        slim = _parse_docker_tag("3.14.0-slim")

        assert current is not None
        assert slim is not None

        # Extract base preferences
        current_base = _extract_base_preference("3.12-alpine3.21")
        slim_base = _extract_base_preference("3.14.0-slim")

        assert current_base == 'alpine'
        assert slim_base == 'slim'
        assert current_base != slim_base  # Different bases!
