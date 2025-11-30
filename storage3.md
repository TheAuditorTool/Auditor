Storage, Data, & Indexer Layer Debugging

Consolidated analysis of Database Managers, Storage Handlers, Schemas, and the Orchestrator.

1. High-Level Architecture Issues

The "Tuple Alignment" Risk

The system relies on base_database.py -> flush_generic_batch to map a list of tuples directly to SQL columns. The add_* methods in database.py must match the exact order and count of the TableSchema definitions in schema.py.

The Danger: If a column is added to the schema but the add_* method is not updated (or vice versa), data is written to the wrong columns or the system crashes.

The "Generic Batch" Blind Spot: The flush_order list in base_database.py is manually maintained. If a table (like resolved_imports) is missing from this list, it never gets flushed to the DB, even if the Extractor adds it to the batch.

The Fidelity "False Negative" Trap

Files: javascript.py, fidelity.py

The Bug: In javascript.py, the manifest is generated based on the result dictionary after key mapping. If the extractor outputs data under a key javascript.py doesn't expect, the result list is empty.

Result: fidelity.py compares "Extracted 0" vs "Stored 0". The check passes, but data was silently lost.

2. Detailed File Analysis

schema.py & Schemas

The Time Bomb: Line 22: assert len(TABLES) == 170. This assertion crashes the system if any table is added or removed.

Missing Table: The resolved_imports table is missing from core_schema.py. This is critical for the Graph layer to function but the storage layer has nowhere to put the data.

react_hooks Mismatch: node_schema.py defines dependency_array as TEXT. Ensure node_database.py handles non-serializable objects in json.dumps to avoid batch failures.

base_database.py

Batch Error Swallowing: flush_batch catches errors but often fails the entire batch if one row is bad.

Fix Needed: Implement a "Safe Flush" mechanism to retry rows individually if a batch insert fails.

core_database.py

Missing Methods: It lacks an add_resolved_import method, meaning javascript.py has no clean way to save the high-fidelity import data it extracts.

Symbol Tuple Mismatch: add_symbol appends 8 items, but CORE_SCHEMA -> SYMBOLS has 9 columns (missing is_typed). This causes an immediate crash.

node_database.py

Missing Methods: Does not implement add_react_component, add_react_hook, or add_vue_component, despite node_storage.py trying to call them.

Drift: add_react_hook logic must strictly match the schema columns (cleanup_type, etc.).

infrastructure_database.py

Missing Methods: Lacks add_dockerfile_port and add_terraform_file despite storage handlers trying to use them.

core_storage.py

Silent Drop: The handlers map in __init__ does not list resolved_imports. Even if the data arrives, the storage layer ignores it.

orchestrator.py

Logic Bloat: Contains hardcoded SQL insertion for security patterns (_seed_express_patterns). These should be moved to a JSON config.

Resolution Conflict: Calls JavaScriptExtractor.resolve_import_paths (Python-based resolution) which overwrites the superior TypeScript resolution.

3. Implementation & Refactoring Plan

Phase 1: Stabilization (Stop Crashes)

Modify schema.py: Comment out assert len(TABLES) == 170.

Patch base_database.py (Safe Flush):

def flush_generic_batch(self, table_name: str, insert_mode: str = "INSERT") -> None:
    try:
        cursor.executemany(query, batch)
    except sqlite3.Error:
        self.conn.rollback()
        print(f"[DB] Batch failed for {table_name}. Retrying row-by-row...", file=sys.stderr)
        for row in batch:
            try:
                cursor.execute(query, row)
            except sqlite3.Error:
                pass 
        self.conn.commit()


Patch core_database.py: Update add_symbol to accept is_typed (default 0) to match the schema.

Phase 2: Fix Data Loss

Update core_schema.py: Add RESOLVED_IMPORTS table definition.

Update base_database.py: Add resolved_imports to flush_order.

Update core_database.py: Add add_resolved_import mixin method.

Update core_storage.py: Add handler: "resolved_imports": self._store_resolved_imports.

Update node_database.py: Implement missing methods (add_react_component, etc.) and ensure json.dumps is wrapped in a safety helper.

Phase 3: Infrastructure & Migration

Update infrastructure_database.py: Add add_terraform_file and Docker methods.

Migration: Delete .pf/graphs.db and run aud index --clean to rebuild with the new schema.