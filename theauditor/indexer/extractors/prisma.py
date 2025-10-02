"""Prisma schema extractor - Database-First Architecture.

Extracts Prisma ORM model definitions from schema.prisma files.
Inlines parsing logic (no separate parser class).

Populates prisma_models table for use by rules/orm/prisma_analyze.py.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor


class PrismaExtractor(BaseExtractor):
    """Extractor for Prisma schema files.

    Parses schema.prisma files to extract model definitions and field metadata.
    Direct database writes via self.db_manager.add_prisma_model().
    """

    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports.

        Prisma schemas don't have a specific extension, match by filename.
        """
        return []  # We handle this specially in should_extract

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.

        Args:
            file_path: Path to the file

        Returns:
            True if this is a schema.prisma file
        """
        file_name_lower = Path(file_path).name.lower()
        return file_name_lower == 'schema.prisma'

    def extract(self, file_info: Dict[str, Any], content: str,
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract Prisma models directly to database.

        Parses schema.prisma content inline (regex-based).
        Writes to prisma_models table via self.db_manager.

        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree (not used for Prisma)

        Returns:
            Minimal dict for indexer compatibility
        """
        try:
            # Parse schema content inline
            models = self._parse_schema(content)

            # Write each model field to database
            for model in models:
                for field in model['fields']:
                    self.db_manager.add_prisma_model(
                        model_name=model['name'],
                        field_name=field['name'],
                        field_type=field['type'],
                        is_indexed=field['is_indexed'],
                        is_unique=field['is_unique'],
                        is_relation=field['is_relation']
                    )

        except Exception:
            # Graceful failure - don't crash indexer
            pass

        # Return minimal dict for indexer compatibility
        return {}

    def _parse_schema(self, content: str) -> List[Dict[str, Any]]:
        """Parse Prisma schema content to extract models.

        Inline parsing logic (copied from prisma_schema_parser.py).
        Uses regex to extract model definitions and fields.

        Args:
            content: schema.prisma file content

        Returns:
            List of model dictionaries with fields
        """
        models = []

        # Parse models using regex
        model_pattern = re.compile(
            r'model\s+(\w+)\s*\{([^}]*)\}',
            re.DOTALL
        )

        for match in model_pattern.finditer(content):
            model_name = match.group(1)
            model_content = match.group(2)

            model = {
                'name': model_name,
                'fields': self._parse_fields(model_content)
            }

            models.append(model)

        return models

    def _parse_fields(self, content: str) -> List[Dict[str, Any]]:
        """Parse fields within a model block.

        Args:
            content: Content inside model { } block

        Returns:
            List of field dictionaries
        """
        fields = []
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('//'):
                continue

            # Skip block attributes (@@)
            if line.startswith('@@'):
                continue

            # Parse field: fieldName Type @attributes
            field_match = re.match(r'^(\w+)\s+(\w+(?:\[\])?(?:\?)?)', line)
            if field_match:
                field_name = field_match.group(1)
                field_type = field_match.group(2)

                field = {
                    'name': field_name,
                    'type': field_type,
                    'is_indexed': False,
                    'is_unique': False,
                    'is_relation': False
                }

                # Check for attributes
                if '@id' in line:
                    field['is_indexed'] = True
                    field['is_unique'] = True

                if '@unique' in line:
                    field['is_unique'] = True
                    field['is_indexed'] = True  # Unique implies indexed

                if '@index' in line:
                    field['is_indexed'] = True

                if '@relation' in line:
                    field['is_relation'] = True

                # Check if it's a relation type (starts with capital letter, not a primitive)
                primitives = {'String', 'Int', 'BigInt', 'Float', 'Boolean', 'DateTime', 'Json', 'Bytes', 'Decimal'}
                base_type = field_type.replace('[]', '').replace('?', '')
                if base_type and base_type[0].isupper() and base_type not in primitives:
                    field['is_relation'] = True

                fields.append(field)

        # Check for composite indexes
        for line in lines:
            line = line.strip()
            if line.startswith('@@index'):
                # Extract field names from composite index
                # @@index([field1, field2])
                index_match = re.search(r'@@index\s*\(\s*\[([^\]]+)\]', line)
                if index_match:
                    indexed_fields = index_match.group(1).split(',')
                    for indexed_field in indexed_fields:
                        indexed_field = indexed_field.strip().strip('"').strip("'")
                        # Mark these fields as indexed
                        for field in fields:
                            if field['name'] == indexed_field:
                                field['is_indexed'] = True

            elif line.startswith('@@unique'):
                # Extract field names from composite unique
                # @@unique([field1, field2])
                unique_match = re.search(r'@@unique\s*\(\s*\[([^\]]+)\]', line)
                if unique_match:
                    unique_fields = unique_match.group(1).split(',')
                    for unique_field in unique_fields:
                        unique_field = unique_field.strip().strip('"').strip("'")
                        # Mark these fields as unique and indexed
                        for field in fields:
                            if field['name'] == unique_field:
                                field['is_unique'] = True
                                field['is_indexed'] = True

        return fields
