"""Utilities for Python ORM-aware taint analysis enhancements."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
import sqlite3
from typing import Dict, List, Optional, Set, Tuple, Iterable, TYPE_CHECKING

from theauditor.indexer.schema import build_query

if TYPE_CHECKING:
    from .memory_cache import MemoryCache


@dataclass
class PythonOrmContext:
    """Lightweight view of Python ORM metadata for taint propagation."""

    model_names: Set[str] = field(default_factory=set)
    table_to_model: Dict[str, str] = field(default_factory=dict)
    relationships: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    fk_fields: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    param_types: Dict[Tuple[str, str, str], str] = field(default_factory=dict)
    cache_assignments_lookup: Optional[Dict[Tuple[str, str], List[Dict[str, str]]]] = None
    cache: Optional["MemoryCache"] = None
    cursor: Optional["sqlite3.Cursor"] = None
    _assignment_cache: Dict[Tuple[str, str], List[Dict[str, str]]] = field(default_factory=dict)

    @classmethod
    def from_cache(cls, cache: "MemoryCache", cursor: Optional["sqlite3.Cursor"]) -> "PythonOrmContext":
        return cls(
            model_names=set(cache.python_model_names),
            table_to_model=dict(cache.python_table_to_model),
            relationships={key: list(vals) for key, vals in cache.python_relationship_aliases.items()},
            fk_fields={key: list(vals) for key, vals in cache.python_fk_fields.items()},
            param_types=dict(cache.python_param_types),
            cache_assignments_lookup=cache.assignments_by_func,
            cache=cache,
            cursor=cursor,
        )

    @classmethod
    def from_database(cls, cursor: "sqlite3.Cursor") -> "PythonOrmContext":
        context = cls(cursor=cursor)
        context._load_models()
        context._load_relationships()
        context._load_fk_fields()
        context._load_param_types()
        return context

    @property
    def enabled(self) -> bool:
        return bool(self.model_names)

    # ----------------------------
    # Cache-backed helpers
    # ----------------------------
    def get_model_for_variable(
        self,
        file_path: str,
        function_names: Iterable[str],
        var_name: str,
        bindings: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        if not var_name:
            return None
        if bindings and var_name in bindings:
            return bindings[var_name]
        if self.cache:
            return self.cache.get_python_model_for_var(
                file_path,
                list(function_names),
                var_name,
                bindings,
            )

        candidates = self._build_function_candidates(function_names)
        for candidate in candidates:
            key = (file_path, candidate, var_name)
            annotation = self.param_types.get(key)
            if annotation:
                resolved = self._resolve_model_from_annotation(annotation)
                if resolved:
                    return resolved

        for candidate in candidates:
            assignments = self._get_assignments(file_path, candidate)
            if not assignments:
                continue
            for assignment in assignments:
                if assignment.get("target_var") == var_name:
                    inferred = self._infer_model_from_assignment(assignment.get("source_expr", ""))
                    if inferred:
                        return inferred
        return None

    def get_relationships(self, model_name: str) -> List[Dict[str, str]]:
        if self.cache:
            return self.cache.get_python_relationships(model_name)
        return self.relationships.get(model_name, [])

    def get_fk_fields(self, model_name: str) -> List[Dict[str, str]]:
        if self.cache:
            return self.cache.get_python_fk_fields(model_name)
        return self.fk_fields.get(model_name, [])

    # ----------------------------
    # Database loading helpers
    # ----------------------------
    def _load_models(self) -> None:
        query = build_query("python_orm_models", ["model_name", "table_name"])
        self.cursor.execute(query)
        for model_name, table_name in self.cursor.fetchall():
            if model_name:
                self.model_names.add(model_name)
            if model_name and table_name:
                self.table_to_model[table_name.lower()] = model_name

    def _load_relationships(self) -> None:
        query = build_query(
            "orm_relationships",
            ["source_model", "target_model", "relationship_type", "as_name", "cascade_delete", "foreign_key"],
        )
        self.cursor.execute(query)
        for source_model, target_model, rel_type, alias, cascade_delete, foreign_key in self.cursor.fetchall():
            if not source_model:
                continue
            entry = {
                "alias": alias or target_model or "",
                "target_model": target_model or "",
                "relationship_type": rel_type or "",
                "cascade_delete": "1" if cascade_delete else "",
                "foreign_key": foreign_key or "",
            }
            self.relationships.setdefault(source_model, []).append(entry)

    def _load_fk_fields(self) -> None:
        query = build_query(
            "python_orm_fields",
            ["model_name", "field_name", "is_foreign_key", "foreign_key_target"],
        )
        self.cursor.execute(query)
        for model_name, field_name, is_fk, fk_target in self.cursor.fetchall():
            if not model_name or not field_name or not is_fk:
                continue
            target_model = self._resolve_model_from_fk_target(fk_target)
            entry = {
                "field_name": field_name,
                "target_model": target_model or "",
                "foreign_key_target": fk_target or "",
            }
            self.fk_fields.setdefault(model_name, []).append(entry)

    def _load_param_types(self) -> None:
        query = build_query(
            "type_annotations",
            ["file", "symbol_name", "type_annotation"],
            where="symbol_kind = 'parameter'",
        )
        self.cursor.execute(query)
        for file_path, symbol_name, annotation in self.cursor.fetchall():
            if not symbol_name:
                continue
            split_result = self._split_symbol_name(symbol_name)
            if not split_result:
                continue
            func_name, param_name = split_result
            for key in self._generate_param_type_keys(file_path, func_name, param_name):
                if key not in self.param_types:
                    self.param_types[key] = annotation

    # ----------------------------
    # Helpers shared between paths
    # ----------------------------
    def _build_function_candidates(self, function_names: Iterable[str]) -> List[str]:
        candidates: List[str] = []
        for func in function_names or []:
            if not func:
                continue
            candidates.extend(self._generate_function_name_candidates(func))
        if not candidates:
            candidates.append("global")
        return candidates

    def _generate_function_name_candidates(self, func_name: str) -> List[str]:
        if not func_name:
            return ["global"]
        parts = [segment for segment in func_name.split(".") if segment]
        if not parts:
            return [func_name]
        variants: List[str] = []
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate:
                variants.append(candidate)
        lower = func_name.lower()
        if lower not in variants:
            variants.append(lower)
        tail = parts[-1]
        if tail not in variants:
            variants.append(tail)
        return variants

    def _split_symbol_name(self, symbol_name: str) -> Optional[Tuple[str, str]]:
        symbol_name = symbol_name.strip()
        if not symbol_name or "." not in symbol_name:
            return None
        func_name, param_name = symbol_name.rsplit(".", 1)
        func_name = func_name.strip()
        param_name = param_name.strip()
        if not func_name or not param_name:
            return None
        return func_name, param_name

    def _generate_param_type_keys(self, file_path: str, func_name: str, param_name: str) -> List[Tuple[str, str, str]]:
        keys = []
        for candidate in self._generate_function_name_candidates(func_name):
            keys.append((file_path, candidate, param_name))
        return keys

    def _resolve_model_from_annotation(self, annotation: Optional[str]) -> Optional[str]:
        if not annotation:
            return None
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation)
        for token in tokens:
            if token in self.model_names:
                return token
            lower = token.lower()
            if lower in self.table_to_model:
                return self.table_to_model[lower]
            capitalized = token[:1].upper() + token[1:]
            if capitalized in self.model_names:
                return capitalized
        return None

    def _resolve_model_from_fk_target(self, fk_target: Optional[str]) -> Optional[str]:
        if not fk_target:
            return None
        normalized = fk_target.strip().strip("'").strip('"')
        if not normalized:
            return None
        table_part = normalized.split(".", 1)[0]
        lower = table_part.lower()
        if lower in self.table_to_model:
            return self.table_to_model[lower]
        if table_part in self.model_names:
            return table_part
        cap = table_part[:1].upper() + table_part[1:]
        if cap in self.model_names:
            return cap
        return None

    def _infer_model_from_assignment(self, source_expr: str) -> Optional[str]:
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", source_expr or "")
        if match:
            candidate = match.group(1)
            if candidate in self.model_names:
                return candidate
        return None

    def _get_assignments(self, file_path: str, func_name: str) -> List[Dict[str, str]]:
        if self.cache_assignments_lookup is not None:
            return self.cache_assignments_lookup.get((file_path, func_name), [])
        key = (file_path, func_name)
        if key in self._assignment_cache:
            return self._assignment_cache[key]
        query = build_query(
            "assignments",
            ["target_var", "source_expr"],
            where="file = ? AND in_function = ?",
        )
        self.cursor.execute(query, (file_path, func_name))
        rows = [
            {"target_var": target or "", "source_expr": source or ""}
            for target, source in self.cursor.fetchall()
        ]
        self._assignment_cache[key] = rows
        return rows


def enhance_python_fk_taint(
    cursor: "sqlite3.Cursor",
    cache: Optional["MemoryCache"],
    tainted_by_function: Dict[str, Dict[str, any]],
) -> None:
    """Augment tainted variable sets using Python ORM relationship metadata."""
    if not tainted_by_function:
        return

    context = PythonOrmContext.from_cache(cache, cursor) if cache else PythonOrmContext.from_database(cursor)
    if not context.enabled:
        return

    for func_name, info in tainted_by_function.items():
        vars_set: Set[str] = info.get("vars", set())
        if not vars_set:
            continue

        file_path = info.get("file")
        if not file_path:
            continue

        display_names = list(info.get("displays", []))
        function_candidates = display_names + ([func_name] if func_name else [])

        bindings: Dict[str, str] = dict(info.get("python_model_bindings", {}))
        processed: Set[str] = set()
        changed = True

        while changed:
            changed = False
            for var in list(vars_set):
                base = var.split(".", 1)[0]
                if base in processed:
                    continue
                model = context.get_model_for_variable(file_path, function_candidates, base, bindings)
                processed.add(base)
                if not model:
                    continue
                if bindings.get(base) != model:
                    bindings[base] = model
                # Expand relationship aliases
                for rel in context.get_relationships(model):
                    alias = rel.get("alias")
                    if not alias:
                        continue
                    dotted = f"{base}.{alias}"
                    if dotted not in vars_set:
                        vars_set.add(dotted)
                        changed = True
                    if alias not in vars_set:
                        vars_set.add(alias)
                        changed = True
                    target_model = rel.get("target_model")
                    if target_model:
                        previous = bindings.get(alias)
                        if previous != target_model:
                            bindings[alias] = target_model
                            processed.discard(alias)
                # Expand FK fields (dotted only)
                for fk in context.get_fk_fields(model):
                    field_name = fk.get("field_name")
                    if not field_name:
                        continue
                    dotted = f"{base}.{field_name}"
                    if dotted not in vars_set:
                        vars_set.add(dotted)
                        changed = True

        if bindings:
            existing = info.setdefault("python_model_bindings", {})
            existing.update(bindings)
