"""GitHub Actions workflow security rules package.

Schema Contract Compliance: v2.0 (Fidelity Layer - Q class + RuleDB)
"""

from .artifact_code_execution import (
    METADATA as ARTIFACT_CODE_EXECUTION_METADATA,
)
from .artifact_code_execution import (
    analyze as analyze_artifact_code_execution,
)
from .artifact_code_execution import (
    find_artifact_code_execution,
)
from .artifact_poisoning import (
    METADATA as ARTIFACT_POISONING_METADATA,
)
from .artifact_poisoning import (
    analyze as analyze_artifact_poisoning,
)
from .artifact_poisoning import (
    find_artifact_poisoning_risk,
)
from .cli_artifact_download import (
    METADATA as CLI_ARTIFACT_DOWNLOAD_METADATA,
)
from .cli_artifact_download import (
    analyze as analyze_cli_artifact_download,
)
from .cli_artifact_download import (
    find_cli_artifact_download,
)
from .excessive_permissions import (
    METADATA as EXCESSIVE_PERMISSIONS_METADATA,
)
from .excessive_permissions import (
    analyze as analyze_excessive_permissions,
)
from .excessive_permissions import (
    find_excessive_pr_permissions,
)
from .reusable_workflow_risks import (
    METADATA as REUSABLE_WORKFLOW_METADATA,
)
from .reusable_workflow_risks import (
    analyze as analyze_reusable_workflow_risks,
)
from .reusable_workflow_risks import (
    find_external_reusable_with_secrets,
)
from .script_injection import (
    METADATA as SCRIPT_INJECTION_METADATA,
)
from .script_injection import (
    analyze as analyze_script_injection,
)
from .script_injection import (
    find_pull_request_injection,
)
from .unpinned_actions import (
    METADATA as UNPINNED_ACTIONS_METADATA,
)
from .unpinned_actions import (
    analyze as analyze_unpinned_actions,
)
from .unpinned_actions import (
    find_unpinned_action_with_secrets,
)
from .untrusted_checkout import (
    METADATA as UNTRUSTED_CHECKOUT_METADATA,
)
from .untrusted_checkout import (
    analyze as analyze_untrusted_checkout,
)
from .untrusted_checkout import (
    find_untrusted_checkout_sequence,
)

__all__ = [
    "analyze_artifact_code_execution",
    "analyze_artifact_poisoning",
    "analyze_cli_artifact_download",
    "analyze_excessive_permissions",
    "analyze_reusable_workflow_risks",
    "analyze_script_injection",
    "analyze_unpinned_actions",
    "analyze_untrusted_checkout",
    "find_artifact_code_execution",
    "find_artifact_poisoning_risk",
    "find_cli_artifact_download",
    "find_excessive_pr_permissions",
    "find_external_reusable_with_secrets",
    "find_pull_request_injection",
    "find_unpinned_action_with_secrets",
    "find_untrusted_checkout_sequence",
    "ARTIFACT_CODE_EXECUTION_METADATA",
    "ARTIFACT_POISONING_METADATA",
    "CLI_ARTIFACT_DOWNLOAD_METADATA",
    "EXCESSIVE_PERMISSIONS_METADATA",
    "REUSABLE_WORKFLOW_METADATA",
    "SCRIPT_INJECTION_METADATA",
    "UNPINNED_ACTIONS_METADATA",
    "UNTRUSTED_CHECKOUT_METADATA",
]
