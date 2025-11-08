"""Access Path abstraction for field-sensitive taint tracking.

IFDS uses access paths of the form x.f.g to track taint through object fields.
This prevents false positives like: req.headers.auth vs req.body.malicious

Based on: "IFDS Taint Analysis with Access Paths" (Allen et al., 2021)
Section 1: Access Paths - page 3
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Set


@dataclass(frozen=True)
class AccessPath:
    """Represents a path through object fields: base.field1.field2...

    Examples:
        req.body.userId  → AccessPath(file="controller.ts", function="create",
                                      base="req", fields=("body", "userId"))
        user.data        → AccessPath(file="service.ts", function="save",
                                      base="user", fields=("data",))
        localVar         → AccessPath(file="util.ts", function="helper",
                                      base="localVar", fields=())

    Attributes:
        file: Source file path
        function: Containing function (or "global")
        base: Base variable name
        fields: Tuple of field names (empty for simple variables)
        max_length: k-limiting bound (default 5)
    """

    file: str
    function: str
    base: str
    fields: Tuple[str, ...]
    max_length: int = 5

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
        path_str = str(self)  # base or base.field1.field2
        return f"{self.file}::{self.function}::{path_str}"

    @staticmethod
    def parse(node_id: str, max_length: int = 5) -> Optional['AccessPath']:
        """Parse graphs.db node ID into AccessPath.

        Format: "file::function::var" or "file::function::var.field1.field2"

        Args:
            node_id: Node ID from graphs.db edges table
            max_length: k-limiting bound (truncate deeper paths)

        Returns:
            AccessPath or None if node_id is invalid

        Examples:
            >>> AccessPath.parse("controller.ts::create::req.body.userId")
            AccessPath(file="controller.ts", function="create",
                      base="req", fields=("body", "userId"))

            >>> AccessPath.parse("service.ts::save::user")
            AccessPath(file="service.ts", function="save",
                      base="user", fields=())
        """
        if not node_id or '::' not in node_id:
            return None

        parts = node_id.split("::")

        # Handle various formats
        if len(parts) < 2:
            return None

        if len(parts) == 2:
            # "file::variable" (global scope)
            file, var_path = parts
            function = "global"
        else:
            # "file::function::variable" or "file::function::var.field"
            file = parts[0]
            function = parts[1]
            var_path = "::".join(parts[2:])  # Handle :: in variable names

        # Parse variable.field.field...
        if not var_path:
            return None

        var_parts = var_path.split(".")
        base = var_parts[0]
        fields = tuple(var_parts[1:]) if len(var_parts) > 1 else ()

        # k-limiting: Truncate fields beyond max_length
        if len(fields) > max_length:
            fields = fields[:max_length]

        return AccessPath(
            file=file,
            function=function,
            base=base,
            fields=fields,
            max_length=max_length
        )

    def matches(self, other: 'AccessPath') -> bool:
        """Check if two access paths could alias (prefix match).

        Conservative approximation: If one is a prefix of the other, assume they alias.

        Examples:
            req.body matches req.body.userId  → True (prefix)
            req.body matches req.headers      → False (different fields)
            user matches user.data            → True (prefix)

        Args:
            other: Another AccessPath to compare

        Returns:
            True if paths could potentially alias
        """
        if self.base != other.base:
            return False

        # Check field prefix match
        min_len = min(len(self.fields), len(other.fields))
        if min_len == 0:
            # One has no fields (just base var) - conservative match
            return True

        return self.fields[:min_len] == other.fields[:min_len]

    def append_field(self, field: str) -> Optional['AccessPath']:
        """Append a field to this access path (with k-limiting).

        Args:
            field: Field name to append

        Returns:
            New AccessPath with field appended, or None if exceeds max_length

        Examples:
            >>> path = AccessPath(..., base="req", fields=("body",))
            >>> path.append_field("userId")
            AccessPath(..., base="req", fields=("body", "userId"))
        """
        if len(self.fields) >= self.max_length:
            return None  # k-limiting: truncate

        return AccessPath(
            file=self.file,
            function=self.function,
            base=self.base,
            fields=self.fields + (field,),
            max_length=self.max_length
        )

    def strip_fields(self, count: int) -> 'AccessPath':
        """Remove N fields from the end (for reification).

        Used in backward analysis when traversing field stores:
            x.f.g = y  →  If tracking x.f.g, reify to y

        Args:
            count: Number of fields to remove

        Returns:
            New AccessPath with fields removed

        Examples:
            >>> path = AccessPath(..., base="x", fields=("f", "g", "h"))
            >>> path.strip_fields(2)
            AccessPath(..., base="x", fields=("f",))
        """
        if count >= len(self.fields):
            # Stripping all fields - just return base
            return AccessPath(
                file=self.file,
                function=self.function,
                base=self.base,
                fields=(),
                max_length=self.max_length
            )

        return AccessPath(
            file=self.file,
            function=self.function,
            base=self.base,
            fields=self.fields[:-count] if count > 0 else self.fields,
            max_length=self.max_length
        )

    def change_base(self, new_base: str) -> 'AccessPath':
        """Replace the base variable (for assignments: x = y.f).

        Args:
            new_base: New base variable name

        Returns:
            New AccessPath with replaced base

        Examples:
            >>> path = AccessPath(..., base="y", fields=("f",))
            >>> path.change_base("x")
            AccessPath(..., base="x", fields=("f",))
        """
        return AccessPath(
            file=self.file,
            function=self.function,
            base=new_base,
            fields=self.fields,
            max_length=self.max_length
        )

    def to_pattern_set(self) -> Set[str]:
        """Convert to set of patterns for legacy taint matching.

        Returns all prefixes for substring matching in existing code.

        Returns:
            Set of pattern strings: {"req", "req.body", "req.body.userId"}

        Examples:
            >>> AccessPath(..., base="req", fields=("body", "userId")).to_pattern_set()
            {"req", "req.body", "req.body.userId"}
        """
        patterns = {self.base}

        current = self.base
        for field in self.fields:
            current += f".{field}"
            patterns.add(current)

        return patterns
