"""GraphQL Rate Limiting Check - Stub implementation."""

from theauditor.rules.base import RuleMetadata, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="graphql_rate_limiting", category="security", execution_scope="database"
)


def check_rate_limiting(context: StandardRuleContext) -> list[StandardFinding]:
    """Check for missing rate limiting on expensive queries."""

    return []
