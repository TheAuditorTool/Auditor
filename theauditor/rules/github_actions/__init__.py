"""GitHub Actions workflow security rules package.

Schema Contract Compliance: v2.0 (Fidelity Layer - Q class + RuleDB)
"""

from .artifact_code_execution import (
    METADATA as ARTIFACT_CODE_EXECUTION_METADATA,
    analyze as analyze_artifact_code_execution,
    find_artifact_code_execution,
)
from .artifact_poisoning import (
    METADATA as ARTIFACT_POISONING_METADATA,
    analyze as analyze_artifact_poisoning,
    find_artifact_poisoning_risk,
)
from .cli_artifact_download import (
    METADATA as CLI_ARTIFACT_DOWNLOAD_METADATA,
    analyze as analyze_cli_artifact_download,
    find_cli_artifact_download,
)
from .excessive_permissions import (
    METADATA as EXCESSIVE_PERMISSIONS_METADATA,
    analyze as analyze_excessive_permissions,
    find_excessive_pr_permissions,
)
from .reusable_workflow_risks import (
    METADATA as REUSABLE_WORKFLOW_METADATA,
    analyze as analyze_reusable_workflow_risks,
    find_external_reusable_with_secrets,
)
from .script_injection import (
    METADATA as SCRIPT_INJECTION_METADATA,
    analyze as analyze_script_injection,
    find_pull_request_injection,
)
from .unpinned_actions import (
    METADATA as UNPINNED_ACTIONS_METADATA,
    analyze as analyze_unpinned_actions,
    find_unpinned_action_with_secrets,
)
from .untrusted_checkout import (
    METADATA as UNTRUSTED_CHECKOUT_METADATA,
    analyze as analyze_untrusted_checkout,
    find_untrusted_checkout_sequence,
)

__all__ = [
    # Analyze functions (new - return RuleResult)
    "analyze_artifact_code_execution",
    "analyze_artifact_poisoning",
    "analyze_cli_artifact_download",
    "analyze_excessive_permissions",
    "analyze_reusable_workflow_risks",
    "analyze_script_injection",
    "analyze_unpinned_actions",
    "analyze_untrusted_checkout",
    # Legacy find_* functions (return list[StandardFinding])
    "find_artifact_code_execution",
    "find_artifact_poisoning_risk",
    "find_cli_artifact_download",
    "find_excessive_pr_permissions",
    "find_external_reusable_with_secrets",
    "find_pull_request_injection",
    "find_unpinned_action_with_secrets",
    "find_untrusted_checkout_sequence",
    # Metadata
    "ARTIFACT_CODE_EXECUTION_METADATA",
    "ARTIFACT_POISONING_METADATA",
    "CLI_ARTIFACT_DOWNLOAD_METADATA",
    "EXCESSIVE_PERMISSIONS_METADATA",
    "REUSABLE_WORKFLOW_METADATA",
    "SCRIPT_INJECTION_METADATA",
    "UNPINNED_ACTIONS_METADATA",
    "UNTRUSTED_CHECKOUT_METADATA",
]
