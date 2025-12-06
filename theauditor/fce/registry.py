"""Semantic Table Registry for FCE.

Categorizes ~148 database tables by their role in convergence analysis.
This enables intelligent querying without writing custom logic for each table.

Table Categories:
    RISK_SOURCES: Tables that flag problems (used for vector detection)
    CONTEXT_PROCESS: Change history / volatility data
    CONTEXT_STRUCTURAL: CFG / complexity data
    CONTEXT_FRAMEWORK: Framework-specific tables (React, Angular, Vue, etc.)
    CONTEXT_SECURITY: Security pattern tables
    CONTEXT_LANGUAGE: Language-specific tables (Python, Go, Rust, Bash)

Query Strategy:
    1. Risk Query (Always): Query RISK_SOURCES for the file
    2. Vector Check (Always): Determine which vectors have data
    3. Context Expansion (Lazy): Only load context tables when requested
"""

from pathlib import Path


class SemanticTableRegistry:
    """Categorizes tables for intelligent querying.

    This registry is static data - no database queries.
    Update as schema evolves.
    """

    RISK_SOURCES: set[str] = {
        "cdk_findings",
        "findings_consolidated",
        "framework_taint_patterns",
        "graphql_findings_cache",
        "python_security_findings",
        "taint_flows",
        "terraform_findings",
    }

    CONTEXT_PROCESS: set[str] = {
        "code_diffs",
        "code_snapshots",
        "refactor_candidates",
        "refactor_history",
    }

    CONTEXT_STRUCTURAL: set[str] = {
        "cfg_block_statements",
        "cfg_block_statements_jsx",
        "cfg_blocks",
        "cfg_blocks_jsx",
        "cfg_edges",
        "cfg_edges_jsx",
    }

    CONTEXT_FRAMEWORK: set[str] = {
        "angular_component_styles",
        "angular_components",
        "angular_guards",
        "angular_module_declarations",
        "angular_module_exports",
        "angular_module_imports",
        "angular_module_providers",
        "angular_modules",
        "angular_services",
        "bullmq_queues",
        "bullmq_workers",
        "express_middleware_chains",
        "graphql_arg_directives",
        "graphql_execution_edges",
        "graphql_field_args",
        "graphql_field_directives",
        "graphql_fields",
        "graphql_resolver_mappings",
        "graphql_resolver_params",
        "graphql_schemas",
        "graphql_types",
        "prisma_models",
        "react_component_hooks",
        "react_components",
        "react_hook_dependencies",
        "react_hooks",
        "sequelize_associations",
        "sequelize_model_fields",
        "sequelize_models",
        "vue_component_emits",
        "vue_component_props",
        "vue_component_setup_returns",
        "vue_components",
        "vue_directives",
        "vue_hooks",
        "vue_provide_inject",
    }

    CONTEXT_SECURITY: set[str] = {
        "api_endpoint_controls",
        "api_endpoints",
        "jwt_patterns",
        "sql_objects",
        "sql_queries",
        "sql_query_tables",
    }

    CONTEXT_LANGUAGE: set[str] = {
        "bash_command_args",
        "bash_commands",
        "bash_control_flows",
        "bash_functions",
        "bash_pipes",
        "bash_redirections",
        "bash_set_options",
        "bash_sources",
        "bash_subshells",
        "bash_variables",
        "go_captured_vars",
        "go_channel_ops",
        "go_channels",
        "go_constants",
        "go_defer_statements",
        "go_error_returns",
        "go_func_params",
        "go_func_returns",
        "go_functions",
        "go_goroutines",
        "go_imports",
        "go_interface_methods",
        "go_interfaces",
        "go_methods",
        "go_middleware",
        "go_packages",
        "go_routes",
        "go_struct_fields",
        "go_structs",
        "go_type_assertions",
        "go_type_params",
        "go_variables",
        "python_branches",
        "python_build_requires",
        "python_class_features",
        "python_collections",
        "python_comprehensions",
        "python_control_statements",
        "python_decorators",
        "python_descriptors",
        "python_django_middleware",
        "python_django_views",
        "python_expressions",
        "python_fixture_params",
        "python_framework_config",
        "python_framework_methods",
        "python_functions_advanced",
        "python_imports_advanced",
        "python_io_operations",
        "python_literals",
        "python_loops",
        "python_operators",
        "python_orm_fields",
        "python_orm_models",
        "python_package_configs",
        "python_package_dependencies",
        "python_protocol_methods",
        "python_protocols",
        "python_routes",
        "python_schema_validators",
        "python_state_mutations",
        "python_stdlib_usage",
        "python_test_cases",
        "python_test_fixtures",
        "python_type_definitions",
        "python_typeddict_fields",
        "python_validation_schemas",
        "python_validators",
        "rust_async_functions",
        "rust_await_points",
        "rust_enum_variants",
        "rust_enums",
        "rust_extern_blocks",
        "rust_extern_functions",
        "rust_functions",
        "rust_generics",
        "rust_impl_blocks",
        "rust_lifetimes",
        "rust_macro_invocations",
        "rust_macros",
        "rust_modules",
        "rust_struct_fields",
        "rust_structs",
        "rust_trait_methods",
        "rust_traits",
        "rust_unsafe_blocks",
        "rust_unsafe_traits",
        "rust_use_statements",
    }

    EXTENSION_TO_PREFIX: dict[str, str] = {
        ".py": "python_",
        ".go": "go_",
        ".rs": "rust_",
        ".sh": "bash_",
        ".bash": "bash_",
    }

    EXTENSION_TO_FRAMEWORKS: dict[str, set[str]] = {
        ".ts": {"react_", "angular_", "vue_", "graphql_", "sequelize_", "prisma_"},
        ".tsx": {"react_", "angular_", "vue_", "graphql_", "sequelize_", "prisma_"},
        ".js": {"react_", "angular_", "vue_", "graphql_", "sequelize_", "prisma_", "express_"},
        ".jsx": {"react_", "graphql_"},
        ".vue": {"vue_"},
    }

    def get_context_tables_for_file(self, file_path: str) -> list[str]:
        """Return relevant context tables based on file extension.

        Args:
            file_path: Path to file (can be relative or absolute)

        Returns:
            Sorted list of table names relevant to this file type
        """
        ext = Path(file_path).suffix.lower()
        tables: list[str] = []

        prefix = self.EXTENSION_TO_PREFIX.get(ext)
        if prefix:
            tables.extend(t for t in self.CONTEXT_LANGUAGE if t.startswith(prefix))

        fw_prefixes = self.EXTENSION_TO_FRAMEWORKS.get(ext, set())
        for fw_prefix in fw_prefixes:
            tables.extend(t for t in self.CONTEXT_FRAMEWORK if t.startswith(fw_prefix))

        return sorted(set(tables))

    def get_all_risk_tables(self) -> list[str]:
        """Return all risk source tables."""
        return sorted(self.RISK_SOURCES)

    def get_all_context_tables(self) -> list[str]:
        """Return all context tables (process + structural + framework + security + language)."""
        all_context = (
            self.CONTEXT_PROCESS
            | self.CONTEXT_STRUCTURAL
            | self.CONTEXT_FRAMEWORK
            | self.CONTEXT_SECURITY
            | self.CONTEXT_LANGUAGE
        )
        return sorted(all_context)

    def get_category_for_table(self, table_name: str) -> str | None:
        """Return the category for a given table name.

        Returns:
            Category name or None if not categorized
        """
        if table_name in self.RISK_SOURCES:
            return "RISK_SOURCES"
        if table_name in self.CONTEXT_PROCESS:
            return "CONTEXT_PROCESS"
        if table_name in self.CONTEXT_STRUCTURAL:
            return "CONTEXT_STRUCTURAL"
        if table_name in self.CONTEXT_FRAMEWORK:
            return "CONTEXT_FRAMEWORK"
        if table_name in self.CONTEXT_SECURITY:
            return "CONTEXT_SECURITY"
        if table_name in self.CONTEXT_LANGUAGE:
            return "CONTEXT_LANGUAGE"
        return None

    @classmethod
    def total_categorized_tables(cls) -> int:
        """Return total number of categorized tables."""
        return (
            len(cls.RISK_SOURCES)
            + len(cls.CONTEXT_PROCESS)
            + len(cls.CONTEXT_STRUCTURAL)
            + len(cls.CONTEXT_FRAMEWORK)
            + len(cls.CONTEXT_SECURITY)
            + len(cls.CONTEXT_LANGUAGE)
        )
