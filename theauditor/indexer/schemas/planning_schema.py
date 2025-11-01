"""
Planning and meta-system schema definitions.

This module contains table schemas for TheAuditor's planning system:
- Plans and tasks (aud planning commands)
- Specs and verification
- Code snapshots and diffs (change tracking)

Design Philosophy:
- Meta-system tables (not code analysis)
- Planning workflow support
- Change history tracking
"""

from typing import Dict
from .utils import Column, ForeignKey, TableSchema


# ============================================================================
# PLANNING TABLES
# ============================================================================

PLANS = TableSchema(
    name="plans",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("name", "TEXT", nullable=False),
        Column("description", "TEXT"),
        Column("created_at", "TEXT", nullable=False),
        Column("status", "TEXT", nullable=False),
        Column("metadata_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        ("idx_plans_status", ["status"]),
        ("idx_plans_created", ["created_at"]),
    ]
)

PLAN_TASKS = TableSchema(
    name="plan_tasks",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("plan_id", "INTEGER", nullable=False),
        Column("task_number", "INTEGER", nullable=False),
        Column("title", "TEXT", nullable=False),
        Column("description", "TEXT"),
        Column("status", "TEXT", nullable=False),
        Column("assigned_to", "TEXT"),
        Column("spec_id", "INTEGER"),
        Column("created_at", "TEXT", nullable=False),
        Column("completed_at", "TEXT"),
    ],
    indexes=[
        ("idx_plan_tasks_plan", ["plan_id"]),
        ("idx_plan_tasks_status", ["status"]),
        ("idx_plan_tasks_spec", ["spec_id"]),
    ],
    unique_constraints=[
        ["plan_id", "task_number"]
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["plan_id"],
            foreign_table="plans",
            foreign_columns=["id"]
        ),
        ForeignKey(
            local_columns=["spec_id"],
            foreign_table="plan_specs",
            foreign_columns=["id"]
        ),
    ]
)

PLAN_SPECS = TableSchema(
    name="plan_specs",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("plan_id", "INTEGER", nullable=False),
        Column("spec_yaml", "TEXT", nullable=False),
        Column("spec_type", "TEXT"),
        Column("created_at", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_plan_specs_plan", ["plan_id"]),
        ("idx_plan_specs_type", ["spec_type"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["plan_id"],
            foreign_table="plans",
            foreign_columns=["id"]
        ),
    ]
)

CODE_SNAPSHOTS = TableSchema(
    name="code_snapshots",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("plan_id", "INTEGER", nullable=False),
        Column("task_id", "INTEGER"),
        Column("sequence", "INTEGER"),
        Column("checkpoint_name", "TEXT", nullable=False),
        Column("timestamp", "TEXT", nullable=False),
        Column("git_ref", "TEXT"),
        Column("files_json", "TEXT", default="'[]'"),
    ],
    indexes=[
        ("idx_code_snapshots_plan", ["plan_id"]),
        ("idx_code_snapshots_task", ["task_id"]),
        ("idx_code_snapshots_task_sequence", ["task_id", "sequence"]),
        ("idx_code_snapshots_timestamp", ["timestamp"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["plan_id"],
            foreign_table="plans",
            foreign_columns=["id"]
        ),
        ForeignKey(
            local_columns=["task_id"],
            foreign_table="plan_tasks",
            foreign_columns=["id"]
        ),
    ]
)

CODE_DIFFS = TableSchema(
    name="code_diffs",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("snapshot_id", "INTEGER", nullable=False),
        Column("file_path", "TEXT", nullable=False),
        Column("diff_text", "TEXT"),
        Column("added_lines", "INTEGER"),
        Column("removed_lines", "INTEGER"),
    ],
    indexes=[
        ("idx_code_diffs_snapshot", ["snapshot_id"]),
        ("idx_code_diffs_file", ["file_path"]),
    ],
    foreign_keys=[
        ForeignKey(
            local_columns=["snapshot_id"],
            foreign_table="code_snapshots",
            foreign_columns=["id"]
        ),
    ]
)

REFACTOR_CANDIDATES = TableSchema(
    name="refactor_candidates",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file_path", "TEXT", nullable=False),
        Column("reason", "TEXT", nullable=False),  # complexity, duplication, size, coupling
        Column("severity", "TEXT", nullable=False),  # low, medium, high, critical
        Column("loc", "INTEGER"),
        Column("cyclomatic_complexity", "INTEGER"),
        Column("duplication_percent", "REAL"),
        Column("num_dependencies", "INTEGER"),
        Column("detected_at", "TEXT", nullable=False),
        Column("metadata_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        ("idx_refactor_candidates_file", ["file_path"]),
        ("idx_refactor_candidates_reason", ["reason"]),
        ("idx_refactor_candidates_severity", ["severity"]),
        ("idx_refactor_candidates_detected", ["detected_at"]),
    ],
    unique_constraints=[
        ["file_path", "reason"]  # One entry per file per reason
    ]
)

REFACTOR_HISTORY = TableSchema(
    name="refactor_history",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("timestamp", "TEXT", nullable=False),
        Column("target_file", "TEXT", nullable=False),
        Column("refactor_type", "TEXT", nullable=False),  # split, rename, consolidate
        Column("migrations_found", "INTEGER"),
        Column("migrations_complete", "INTEGER"),
        Column("schema_consistent", "INTEGER"),  # SQLite uses INTEGER for BOOLEAN
        Column("validation_status", "TEXT"),
        Column("details_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        ("idx_refactor_history_file", ["target_file"]),
        ("idx_refactor_history_type", ["refactor_type"]),
        ("idx_refactor_history_timestamp", ["timestamp"]),
    ]
)

# ============================================================================
# PLANNING TABLES REGISTRY
# ============================================================================

PLANNING_TABLES: Dict[str, TableSchema] = {
    "plans": PLANS,
    "plan_tasks": PLAN_TASKS,
    "plan_specs": PLAN_SPECS,
    "code_snapshots": CODE_SNAPSHOTS,
    "code_diffs": CODE_DIFFS,
    "refactor_candidates": REFACTOR_CANDIDATES,
    "refactor_history": REFACTOR_HISTORY,
}
