"""Utilities for Python ORM-aware taint analysis enhancements."""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from theauditor.indexer.schema import build_query

if TYPE_CHECKING:
    from .memory_cache import MemoryCache


@dataclass
class PythonOrmContext:
    """Lightweight view of Python ORM metadata for taint propagation."""

    model_names: set[str] = field(default_factory=set)
    table_to_model: dict[str, str] = field(default_factory=dict)
    relationships: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    fk_fields: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    param_types: dict[tuple[str, str, str], str] = field(default_factory=dict)
    cache_assignments_lookup: dict[tuple[str, str], list[dict[str, str]]] | None = None
    cache: MemoryCache | None = None
    cursor: sqlite3.Cursor | None = None
    _assignment_cache: dict[tuple[str, str], list[dict[str, str]]] = field(default_factory=dict)

    @classmethod
    def from_cache(cls, cache: MemoryCache, cursor: sqlite3.Cursor | None) -> PythonOrmContext:
        return cls(
            model_names=set(cache.python_model_names),
            table_to_model=dict(cache.python_table_to_model),
            relationships={
                key: list(vals) for key, vals in cache.python_relationship_aliases.items()
            },
            fk_fields={key: list(vals) for key, vals in cache.python_fk_fields.items()},
            param_types=dict(cache.python_param_types),
            cache_assignments_lookup=cache.assignments_by_func,
            cache=cache,
            cursor=cursor,
        )

    @classmethod
    def from_database(cls, cursor: sqlite3.Cursor) -> PythonOrmContext:
        context = cls(cursor=cursor)
        context._load_models()
        context._load_relationships()
        context._load_fk_fields()
        context._load_param_types()
        return context

    @property
    def enabled(self) -> bool:
        return bool(self.model_names)

    def get_model_for_variable(
        self,
        file_path: str,
        function_names: Iterable[str],
        var_name: str,
        bindings: dict[str, str] | None = None,
    ) -> str | None:
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

    def get_relationships(self, model_name: str) -> list[dict[str, str]]:
        if self.cache:
            return self.cache.get_python_relationships(model_name)
        return self.relationships.get(model_name, [])

    def get_fk_fields(self, model_name: str) -> list[dict[str, str]]:
        if self.cache:
            return self.cache.get_python_fk_fields(model_name)
        return self.fk_fields.get(model_name, [])

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
            [
                "source_model",
                "target_model",
                "relationship_type",
                "as_name",
                "cascade_delete",
                "foreign_key",
            ],
        )
        self.cursor.execute(query)
        for (
            source_model,
            target_model,
            rel_type,
            alias,
            cascade_delete,
            foreign_key,
        ) in self.cursor.fetchall():
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

    def _build_function_candidates(self, function_names: Iterable[str]) -> list[str]:
        candidates: list[str] = []
        for func in function_names or []:
            if not func:
                continue
            candidates.extend(self._generate_function_name_candidates(func))
        if not candidates:
            candidates.append("global")
        return candidates

    def _generate_function_name_candidates(self, func_name: str) -> list[str]:
        if not func_name:
            return ["global"]
        parts = [segment for segment in func_name.split(".") if segment]
        if not parts:
            return [func_name]
        variants: list[str] = []
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

    def _split_symbol_name(self, symbol_name: str) -> tuple[str, str] | None:
        symbol_name = symbol_name.strip()
        if not symbol_name or "." not in symbol_name:
            return None
        func_name, param_name = symbol_name.rsplit(".", 1)
        func_name = func_name.strip()
        param_name = param_name.strip()
        if not func_name or not param_name:
            return None
        return func_name, param_name

    def _generate_param_type_keys(
        self, file_path: str, func_name: str, param_name: str
    ) -> list[tuple[str, str, str]]:
        keys = []
        for candidate in self._generate_function_name_candidates(func_name):
            keys.append((file_path, candidate, param_name))
        return keys

    def _resolve_model_from_annotation(self, annotation: str | None) -> str | None:
        if not annotation:
            return None

        annotation_clean = (
            annotation.replace("[", " ")
            .replace("]", " ")
            .replace(",", " ")
            .replace("(", " ")
            .replace(")", " ")
        )
        tokens = [t.strip() for t in annotation_clean.split() if t.strip()]

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

    def _resolve_model_from_fk_target(self, fk_target: str | None) -> str | None:
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

    def _infer_model_from_assignment(self, source_expr: str) -> str | None:
        if not source_expr:
            return None

        expr = source_expr.strip()
        if "(" not in expr:
            return None

        candidate = expr.split("(")[0].strip()

        if not candidate or not (candidate[0].isalpha() or candidate[0] == "_"):
            return None

        if candidate in self.model_names:
            return candidate
        return None

    def _get_assignments(self, file_path: str, func_name: str) -> list[dict[str, str]]:
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
