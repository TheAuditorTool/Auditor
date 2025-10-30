"""Python-specific memory cache loading and indexing.

This module handles all Python-specific data loading for the memory cache,
including ORM models, routes, validators, and type annotations.

Extracted from memory_cache.py to reduce monolith size and improve maintainability.
"""

from __future__ import annotations

import sys
import json
import re
import sqlite3
from typing import Dict, List, Any, Optional, Tuple, Set, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from .memory_cache import MemoryCache

from theauditor.indexer.schema import build_query


class PythonMemoryCacheLoader:
    """Handles Python-specific memory cache loading and indexing."""

    def __init__(self, parent_cache: 'MemoryCache'):
        """Initialize with reference to parent MemoryCache instance.

        Args:
            parent_cache: Parent MemoryCache instance for accessing shared structures
        """
        self.parent = parent_cache

        # Python-specific framework tables (Phase 3 Python parity)
        self.python_orm_models: List[Dict[str, Any]] = []
        self.python_orm_fields: List[Dict[str, Any]] = []
        self.orm_relationships: List[Dict[str, Any]] = []
        self.python_routes: List[Dict[str, Any]] = []
        self.python_blueprints: List[Dict[str, Any]] = []
        self.python_validators: List[Dict[str, Any]] = []

        # Python-specific indexes for fast ORM / route lookups
        self.python_orm_models_by_file = defaultdict(list)
        self.python_orm_models_by_name = defaultdict(list)
        self.python_orm_fields_by_model = defaultdict(list)
        self.orm_relationships_by_source = defaultdict(list)
        self.orm_relationships_by_target = defaultdict(list)
        self.python_routes_by_file = defaultdict(list)
        self.python_routes_by_framework = defaultdict(list)
        self.python_validators_by_model = defaultdict(list)
        self.python_validators_by_file = defaultdict(list)
        self.python_blueprints_by_name = defaultdict(list)

        # Python type annotation + ORM metadata
        self.type_annotations: List[Dict[str, Any]] = []
        self.type_annotations_by_file = defaultdict(list)
        self.python_param_types: Dict[Tuple[str, str, str], str] = {}
        self.python_model_names: Set[str] = set()
        self.python_table_to_model: Dict[str, str] = {}
        self.python_relationship_aliases = defaultdict(list)  # model -> [relationship dict]
        self.python_fk_fields = defaultdict(list)  # model -> [field dict]

    def load_python_data(self, cursor: sqlite3.Cursor) -> None:
        """Load all Python-specific tables into memory.

        This is called by MemoryCache.preload() as part of the full database load.

        Args:
            cursor: SQLite cursor for database queries
        """
        self._load_orm_models(cursor)
        self._load_orm_fields(cursor)
        self._load_relationships(cursor)
        self._load_routes(cursor)
        self._load_blueprints(cursor)
        self._load_validators(cursor)
        self._load_type_annotations(cursor)

    def _load_orm_models(self, cursor: sqlite3.Cursor) -> None:
        """Load Python ORM models (SQLAlchemy, Django)."""
        query = build_query('python_orm_models', [
            'file', 'line', 'model_name', 'table_name', 'orm_type'
        ])
        cursor.execute(query)
        python_orm_models_data = cursor.fetchall()

        for file, line, model_name, table_name, orm_type in python_orm_models_data:
            file = file.replace("\\", "/") if file else ""
            model_name = model_name or ""
            table_name = table_name or ""
            model = {
                "file": file,
                "line": line or 0,
                "model_name": model_name,
                "table_name": table_name,
                "orm_type": orm_type or "sqlalchemy",
            }
            self.python_orm_models.append(model)
            self.python_orm_models_by_file[file].append(model)
            self.python_orm_models_by_name[model_name].append(model)
            self.parent.current_memory += sys.getsizeof(model) + 50
            if model_name:
                self.python_model_names.add(model_name)
            if table_name:
                self.python_table_to_model[table_name.lower()] = model_name

        print(f"[MEMORY] Loaded {len(self.python_orm_models)} Python ORM models", file=sys.stderr)

    def _load_orm_fields(self, cursor: sqlite3.Cursor) -> None:
        """Load Python ORM model fields."""
        query = build_query('python_orm_fields', [
            'file', 'line', 'model_name', 'field_name', 'field_type',
            'is_primary_key', 'is_foreign_key', 'foreign_key_target'
        ])
        cursor.execute(query)
        python_orm_fields_data = cursor.fetchall()

        for file, line, model_name, field_name, field_type, is_pk, is_fk, fk_target in python_orm_fields_data:
            file = file.replace("\\", "/") if file else ""
            model_name = model_name or ""
            field = {
                "file": file,
                "line": line or 0,
                "model_name": model_name or "",
                "field_name": field_name or "",
                "field_type": field_type or "",
                "is_primary_key": bool(is_pk),
                "is_foreign_key": bool(is_fk),
                "foreign_key_target": fk_target or "",
            }
            target_model = self._resolve_model_from_fk_target(fk_target)
            field["target_model"] = target_model or ""
            self.python_orm_fields.append(field)
            self.python_orm_fields_by_model[model_name].append(field)
            if target_model:
                self.python_fk_fields[model_name].append({
                    "field_name": field_name or "",
                    "target_model": target_model,
                    "foreign_key_target": fk_target or "",
                })
            self.parent.current_memory += sys.getsizeof(field) + 50

        print(f"[MEMORY] Loaded {len(self.python_orm_fields)} Python ORM fields", file=sys.stderr)

    def _load_relationships(self, cursor: sqlite3.Cursor) -> None:
        """Load ORM relationships (bidirectional)."""
        query = build_query('orm_relationships', [
            'file', 'line', 'source_model', 'target_model', 'relationship_type',
            'foreign_key', 'cascade_delete', 'as_name'
        ])
        cursor.execute(query)
        orm_relationship_data = cursor.fetchall()

        for (
            file,
            line,
            source_model,
            target_model,
            rel_type,
            foreign_key,
            cascade_delete,
            alias,
        ) in orm_relationship_data:
            file = file.replace("\\", "/") if file else ""
            rel = {
                "file": file,
                "line": line or 0,
                "source_model": source_model or "",
                "target_model": target_model or "",
                "relationship_type": rel_type or "",
                "foreign_key": foreign_key or "",
                "cascade_delete": bool(cascade_delete),
                "as_name": alias or "",
            }
            self.orm_relationships.append(rel)
            self.orm_relationships_by_source[source_model].append(rel)
            self.orm_relationships_by_target[target_model].append(rel)
            self.parent.current_memory += sys.getsizeof(rel) + 50
            alias_name = alias or target_model or ""
            if source_model and alias_name:
                self.python_relationship_aliases[source_model].append({
                    "alias": alias_name,
                    "target_model": target_model or "",
                    "relationship_type": rel_type or "",
                    "cascade_delete": bool(cascade_delete),
                    "foreign_key": foreign_key or "",
                })

        print(f"[MEMORY] Loaded {len(self.orm_relationships)} ORM relationships", file=sys.stderr)

    def _load_routes(self, cursor: sqlite3.Cursor) -> None:
        """Load Python web framework routes (FastAPI, Flask)."""
        query = build_query('python_routes', [
            'file', 'line', 'framework', 'method', 'pattern',
            'handler_function', 'has_auth', 'dependencies', 'blueprint'
        ])
        cursor.execute(query)
        python_routes_data = cursor.fetchall()

        for (
            file,
            line,
            framework,
            method,
            pattern,
            handler_function,
            has_auth,
            dependencies,
            blueprint,
        ) in python_routes_data:
            file = file.replace("\\", "/") if file else ""
            deps_list: List[str] = []
            if dependencies:
                try:
                    deps_list = json.loads(dependencies)
                except Exception:
                    deps_list = []
            route = {
                "file": file,
                "line": line or 0,
                "framework": framework or "",
                "method": method or "",
                "pattern": pattern or "",
                "handler_function": handler_function or "",
                "has_auth": bool(has_auth),
                "dependencies": deps_list,
                "blueprint": blueprint or "",
            }
            self.python_routes.append(route)
            self.python_routes_by_file[file].append(route)
            self.python_routes_by_framework[framework].append(route)
            self.parent.current_memory += sys.getsizeof(route) + 50

        print(f"[MEMORY] Loaded {len(self.python_routes)} Python routes", file=sys.stderr)

    def _load_blueprints(self, cursor: sqlite3.Cursor) -> None:
        """Load Flask blueprints."""
        query = build_query('python_blueprints', [
            'file', 'line', 'blueprint_name', 'url_prefix', 'subdomain'
        ])
        cursor.execute(query)
        python_blueprints_data = cursor.fetchall()

        for file, line, blueprint_name, url_prefix, subdomain in python_blueprints_data:
            file = file.replace("\\", "/") if file else ""
            blueprint_entry = {
                "file": file,
                "line": line or 0,
                "blueprint_name": blueprint_name or "",
                "url_prefix": url_prefix or "",
                "subdomain": subdomain or "",
            }
            self.python_blueprints.append(blueprint_entry)
            self.python_blueprints_by_name[blueprint_name].append(blueprint_entry)
            self.parent.current_memory += sys.getsizeof(blueprint_entry) + 50

        print(f"[MEMORY] Loaded {len(self.python_blueprints)} Python blueprints", file=sys.stderr)

    def _load_validators(self, cursor: sqlite3.Cursor) -> None:
        """Load Pydantic validators."""
        query = build_query('python_validators', [
            'file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'
        ])
        cursor.execute(query)
        python_validators_data = cursor.fetchall()

        for file, line, model_name, field_name, validator_method, validator_type in python_validators_data:
            file = file.replace("\\", "/") if file else ""
            validator = {
                "file": file,
                "line": line or 0,
                "model_name": model_name or "",
                "field_name": field_name or "",
                "validator_method": validator_method or "",
                "validator_type": validator_type or "",
            }
            self.python_validators.append(validator)
            self.python_validators_by_model[model_name].append(validator)
            self.python_validators_by_file[file].append(validator)
            self.parent.current_memory += sys.getsizeof(validator) + 50

        print(f"[MEMORY] Loaded {len(self.python_validators)} Python validators", file=sys.stderr)

    def _load_type_annotations(self, cursor: sqlite3.Cursor) -> None:
        """Load type annotations for Python model resolution."""
        query = build_query('type_annotations', [
            'file', 'line', 'symbol_name', 'symbol_kind', 'type_annotation', 'return_type'
        ])
        cursor.execute(query)
        type_annotations_data = cursor.fetchall()

        for file, line, symbol_name, symbol_kind, type_annotation, return_type in type_annotations_data:
            file = file.replace("\\", "/") if file else ""
            entry = {
                "file": file,
                "line": line or 0,
                "symbol_name": symbol_name or "",
                "symbol_kind": symbol_kind or "",
                "type_annotation": type_annotation or "",
                "return_type": return_type or "",
            }
            self.type_annotations.append(entry)
            self.type_annotations_by_file[file].append(entry)
            self.parent.current_memory += sys.getsizeof(entry) + 50

            if entry["symbol_kind"] == "parameter" and entry["symbol_name"]:
                split_result = self._split_symbol_name(entry["symbol_name"])
                if split_result:
                    func_candidate, param_name = split_result
                    for key in self._generate_param_type_keys(file, func_candidate, param_name):
                        if key not in self.python_param_types:
                            self.python_param_types[key] = entry["type_annotation"]

    # Helper methods for model resolution and type inference

    def _resolve_model_from_fk_target(self, fk_target: Optional[str]) -> Optional[str]:
        """Resolve model name from ForeignKey target string."""
        if not fk_target:
            return None
        target = fk_target.strip().strip('"').strip("'")
        if not target:
            return None
        table_part = target.split(".", 1)[0]
        table_lookup = table_part.lower()
        if table_lookup in self.python_table_to_model:
            return self.python_table_to_model[table_lookup]
        if table_part in self.python_model_names:
            return table_part
        capitalized = table_part[:1].upper() + table_part[1:]
        if capitalized in self.python_model_names:
            return capitalized
        return None

    def _split_symbol_name(self, symbol_name: str) -> Optional[Tuple[str, str]]:
        """Split symbol_name into function/method and parameter components."""
        if not symbol_name or "." not in symbol_name:
            return None
        func_name, param_name = symbol_name.rsplit(".", 1)
        func_name = func_name.strip()
        param_name = param_name.strip()
        if not func_name or not param_name:
            return None
        return func_name, param_name

    def _generate_param_type_keys(self, file_path: str, func_name: str, param_name: str) -> List[Tuple[str, str, str]]:
        """Generate lookup keys for parameter type annotations with fallbacks."""
        candidates = []
        if func_name:
            candidates.extend(self._generate_function_name_candidates(func_name))
        else:
            candidates.append("global")
        unique = []
        seen = set()
        for candidate in candidates:
            key = (file_path, candidate, param_name)
            if key not in seen:
                seen.add(key)
                unique.append(key)
        return unique

    def _generate_function_name_candidates(self, func_name: str) -> List[str]:
        """Generate function name variants for lookups (full, suffixes, lowercase)."""
        if not func_name:
            return ["global"]
        parts = [segment for segment in func_name.split(".") if segment]
        if not parts:
            return [func_name]
        candidates: List[str] = []
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate:
                candidates.append(candidate)
        lower = func_name.lower()
        if lower not in candidates:
            candidates.append(lower)
        if parts[-1] not in candidates:
            candidates.append(parts[-1])
        return candidates

    def _infer_model_from_assignment(self, assignment: Dict[str, Any]) -> Optional[str]:
        """Infer model type from assignment source expression (e.g., Model())."""
        source_expr = assignment.get("source_expr") or ""
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", source_expr)
        if match:
            candidate = match.group(1)
            if candidate in self.python_model_names:
                return candidate
        return None

    def resolve_python_model_from_annotation(self, annotation: Optional[str]) -> Optional[str]:
        """Resolve a model name from a type annotation string."""
        if not annotation:
            return None
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation)
        for token in tokens:
            if token in self.python_model_names:
                return token
            lower = token.lower()
            if lower in self.python_table_to_model:
                return self.python_table_to_model[lower]
            capitalized = token[:1].upper() + token[1:]
            if capitalized in self.python_model_names:
                return capitalized
        return None

    def get_python_model_for_var(
        self,
        file_path: str,
        function_names: List[str],
        var_name: str,
        existing_bindings: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Resolve Python ORM model for a variable using annotations or assignments."""
        if not var_name:
            return None
        if existing_bindings and var_name in existing_bindings:
            return existing_bindings[var_name]

        candidates = []
        for func in function_names or []:
            candidates.extend(self._generate_function_name_candidates(func))
        if not candidates:
            candidates.append("global")

        for func_candidate in candidates:
            key = (file_path, func_candidate, var_name)
            if key in self.python_param_types:
                model = self.resolve_python_model_from_annotation(self.python_param_types[key])
                if model:
                    return model

        # Fallback: inspect assignments within candidate functions
        for func_candidate in candidates:
            assignments = self.parent.assignments_by_func.get((file_path, func_candidate))
            if not assignments and func_candidate.endswith(".py"):
                assignments = self.parent.assignments_by_func.get((file_path, "global"))
            if not assignments:
                continue
            for assignment in assignments:
                if assignment.get("target_var") == var_name:
                    model = self._infer_model_from_assignment(assignment)
                    if model:
                        return model

        return None

    def get_python_relationships(self, model_name: str) -> List[Dict[str, Any]]:
        """Return relationship definitions for a Python ORM model."""
        return self.python_relationship_aliases.get(model_name, [])

    def get_python_fk_fields(self, model_name: str) -> List[Dict[str, Any]]:
        """Return foreign key field definitions for a model."""
        return self.python_fk_fields.get(model_name, [])
