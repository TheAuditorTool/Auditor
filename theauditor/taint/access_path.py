"""Access Path abstraction for field-sensitive taint tracking."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessPath:
    """Represents a path through object fields: base.field1.field2..."""

    file: str
    function: str
    base: str
    fields: tuple[str, ...]
    max_length: int = 20

    def __post_init__(self):
        """Normalize file path to Unix-style (forward slashes).

        This ensures AccessPath('a\\b') == AccessPath('a/b').
        Required for Windows/WSL environments where extractors may produce mixed paths.
        """
        if self.file and "\\" in self.file:
            object.__setattr__(self, "file", self.file.replace("\\", "/"))

    def __str__(self) -> str:
        """Human-readable representation."""
        if not self.fields:
            return self.base
        return f"{self.base}.{'.'.join(self.fields)}"

    def __repr__(self) -> str:
        """Debug representation."""
        return f"AccessPath({self.file}::{self.function}::{self})"

    @property
    def node_id(self) -> str:
        """Convert to graphs.db node ID format: file::function::var.field"""
        path_str = str(self)
        return f"{self.file}::{self.function}::{path_str}"

    @staticmethod
    def parse(node_id: str, max_length: int = 20) -> AccessPath | None:
        """Parse graphs.db node ID into AccessPath."""
        if not node_id or "::" not in node_id:
            return None

        parts = node_id.split("::")

        if len(parts) < 2:
            return None

        if len(parts) == 2:
            file, var_path = parts
            function = "global"
        else:
            file = parts[0]
            var_path = parts[-1]
            function = "::".join(parts[1:-1]) if len(parts) > 2 else ""

        if not var_path:
            return None

        var_parts = var_path.split(".")
        base = var_parts[0]
        fields = tuple(var_parts[1:]) if len(var_parts) > 1 else ()

        if len(fields) > max_length:
            fields = fields[:max_length]

        return AccessPath(
            file=file, function=function, base=base, fields=fields, max_length=max_length
        )

    def matches(self, other: AccessPath) -> bool:
        """Check if two access paths could alias (prefix match)."""
        if self.base != other.base:
            return False

        min_len = min(len(self.fields), len(other.fields))
        if min_len == 0:
            return True

        return self.fields[:min_len] == other.fields[:min_len]

    def append_field(self, field: str) -> AccessPath | None:
        """Append a field to this access path (with k-limiting)."""
        if len(self.fields) >= self.max_length:
            return None

        return AccessPath(
            file=self.file,
            function=self.function,
            base=self.base,
            fields=self.fields + (field,),
            max_length=self.max_length,
        )

    def strip_fields(self, count: int) -> AccessPath:
        """Remove N fields from the end (for reification)."""
        if count >= len(self.fields):
            return AccessPath(
                file=self.file,
                function=self.function,
                base=self.base,
                fields=(),
                max_length=self.max_length,
            )

        return AccessPath(
            file=self.file,
            function=self.function,
            base=self.base,
            fields=self.fields[:-count] if count > 0 else self.fields,
            max_length=self.max_length,
        )

    def change_base(self, new_base: str) -> AccessPath:
        """Replace the base variable (for assignments: x = y.f)."""
        return AccessPath(
            file=self.file,
            function=self.function,
            base=new_base,
            fields=self.fields,
            max_length=self.max_length,
        )

    def to_pattern_set(self) -> set[str]:
        """Convert to set of patterns for legacy taint matching."""
        patterns = {self.base}

        current = self.base
        for field in self.fields:
            current += f".{field}"
            patterns.add(current)

        return patterns
