"""Node.js storage handlers for JavaScript/TypeScript frameworks.

This module contains handlers for JavaScript/TypeScript frameworks:
- React: hooks (components in core)
- Vue: components, hooks, directives, provide/inject
- Angular: components, services, modules, guards, DI
- ORM: sequelize models/associations
- Queue: bullmq queues/workers
- Build: import styles, lock analysis

Handler Count: 16
"""


from .base import BaseStorage


class NodeStorage(BaseStorage):
    """Node.js/JavaScript framework storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            'react_hooks': self._store_react_hooks,
            'vue_components': self._store_vue_components,
            'vue_hooks': self._store_vue_hooks,
            'vue_directives': self._store_vue_directives,
            'vue_provide_inject': self._store_vue_provide_inject,
            # Vue junction arrays (normalize-node-extractor-output)
            'vue_component_props': self._store_vue_component_props,
            'vue_component_emits': self._store_vue_component_emits,
            'vue_component_setup_returns': self._store_vue_component_setup_returns,
            'sequelize_models': self._store_sequelize_models,
            'sequelize_associations': self._store_sequelize_associations,
            'bullmq_queues': self._store_bullmq_queues,
            'bullmq_workers': self._store_bullmq_workers,
            'angular_components': self._store_angular_components,
            'angular_services': self._store_angular_services,
            'angular_modules': self._store_angular_modules,
            'angular_guards': self._store_angular_guards,
            'di_injections': self._store_di_injections,
            # Angular junction arrays (normalize-node-extractor-output)
            'angular_component_styles': self._store_angular_component_styles,
            'angular_module_declarations': self._store_angular_module_declarations,
            'angular_module_imports': self._store_angular_module_imports,
            'angular_module_providers': self._store_angular_module_providers,
            'angular_module_exports': self._store_angular_module_exports,
            'lock_analysis': self._store_lock_analysis,
            'import_styles': self._store_import_styles,
            'frontend_api_calls': self._store_frontend_api_calls
        }

    def _store_react_hooks(self, file_path: str, react_hooks: list, jsx_pass: bool):
        """Store React hooks."""
        for hook in react_hooks:
            self.db_manager.add_react_hook(
                file_path,
                hook['line'],
                hook['component_name'],
                hook['hook_name'],
                hook.get('dependency_array'),
                hook.get('dependency_vars'),
                hook.get('callback_body'),
                hook.get('has_cleanup', False),
                hook.get('cleanup_type')
            )
            self.counts['react_hooks'] += 1

    def _store_vue_components(self, file_path: str, vue_components: list, jsx_pass: bool):
        """Store Vue component PARENT RECORDS ONLY.

        Junction data (props, emits, setup_returns) stored via dedicated handlers:
        - _store_vue_component_props()
        - _store_vue_component_emits()
        - _store_vue_component_setup_returns()
        """
        for component in vue_components:
            self.db_manager.add_vue_component(
                file_path,
                component['name'],
                component['type'],
                component['start_line'],
                component['end_line'],
                component.get('has_template', False),
                component.get('has_style', False),
                component.get('composition_api_used', False)
                # REMOVED: props_definition, emits_definition, setup_return
                # Junction data now via dedicated handlers
            )
            if 'vue_components' not in self.counts:
                self.counts['vue_components'] = 0
            self.counts['vue_components'] += 1

    def _store_vue_hooks(self, file_path: str, vue_hooks: list, jsx_pass: bool):
        """Store Vue hooks."""
        for hook in vue_hooks:
            self.db_manager.add_vue_hook(
                file_path,
                hook['line'],
                hook['component_name'],
                hook['hook_name'],
                hook.get('hook_type', 'unknown'),
                hook.get('dependencies'),
                hook.get('return_value'),
                hook.get('is_async', False)
            )
            if 'vue_hooks' not in self.counts:
                self.counts['vue_hooks'] = 0
            self.counts['vue_hooks'] += 1

    def _store_vue_directives(self, file_path: str, vue_directives: list, jsx_pass: bool):
        """Store Vue directives."""
        for directive in vue_directives:
            self.db_manager.add_vue_directive(
                file_path,
                directive['line'],
                directive['directive_name'],
                directive.get('value_expr', ''),
                directive.get('in_component', 'global'),
                directive.get('is_dynamic', False),
                directive.get('modifiers')
            )
            if 'vue_directives' not in self.counts:
                self.counts['vue_directives'] = 0
            self.counts['vue_directives'] += 1

    def _store_vue_provide_inject(self, file_path: str, vue_provide_inject: list, jsx_pass: bool):
        """Store Vue provide/inject."""
        for pi in vue_provide_inject:
            self.db_manager.add_vue_provide_inject(
                file_path,
                pi['line'],
                pi['component_name'],
                pi.get('operation_type', 'unknown'),
                pi.get('key_name', ''),
                pi.get('value_expr'),
                pi.get('is_reactive', False)
            )

    def _store_sequelize_models(self, file_path: str, sequelize_models: list, jsx_pass: bool):
        """Store Sequelize model definitions."""
        for model in sequelize_models:
            # Handle both dict and string formats
            model_data = {'model_name': model, 'line': 0} if isinstance(model, str) else model

            self.db_manager.add_sequelize_model(
                file_path,
                model_data.get('line', 0),
                model_data.get('model_name', ''),
                model_data.get('table_name'),
                model_data.get('extends_model', False)
            )
            self.counts['sequelize_models'] = self.counts.get('sequelize_models', 0) + 1

    def _store_sequelize_associations(self, file_path: str, sequelize_associations: list, jsx_pass: bool):
        """Store Sequelize model associations."""
        for assoc in sequelize_associations:
            self.db_manager.add_sequelize_association(
                file_path,
                assoc.get('line', 0),
                assoc.get('model_name', ''),
                assoc.get('association_type', ''),
                assoc.get('target_model', ''),
                assoc.get('foreign_key'),
                assoc.get('through_table')
            )
            self.counts['sequelize_associations'] = self.counts.get('sequelize_associations', 0) + 1

    def _store_bullmq_queues(self, file_path: str, bullmq_queues: list, jsx_pass: bool):
        """Store BullMQ queue definitions."""
        for queue in bullmq_queues:
            # NOTE: extractor returns 'name', we map to 'queue_name'
            self.db_manager.add_bullmq_queue(
                file_path,
                queue.get('line', 0),
                queue.get('name', ''),
                queue.get('redis_config')
            )
            self.counts['bullmq_queues'] = self.counts.get('bullmq_queues', 0) + 1

    def _store_bullmq_workers(self, file_path: str, bullmq_workers: list, jsx_pass: bool):
        """Store BullMQ worker definitions."""
        for worker in bullmq_workers:
            self.db_manager.add_bullmq_worker(
                file_path,
                worker.get('line', 0),
                worker.get('queue_name', ''),
                worker.get('worker_function'),
                worker.get('processor_path')
            )
            self.counts['bullmq_workers'] = self.counts.get('bullmq_workers', 0) + 1

    def _store_angular_components(self, file_path: str, angular_components: list, jsx_pass: bool):
        """Store Angular component definitions."""
        for component in angular_components:
            # NOTE: extractor returns 'name', we map to 'component_name'
            self.db_manager.add_angular_component(
                file_path,
                component.get('line', 0),
                component.get('name', ''),
                component.get('selector'),
                component.get('template_path'),
                component.get('style_paths'),
                component.get('has_lifecycle_hooks', False)
            )
            self.counts['angular_components'] = self.counts.get('angular_components', 0) + 1

    def _store_angular_services(self, file_path: str, angular_services: list, jsx_pass: bool):
        """Store Angular service definitions."""
        for service in angular_services:
            # NOTE: extractor returns 'name', we map to 'service_name'
            self.db_manager.add_angular_service(
                file_path,
                service.get('line', 0),
                service.get('name', ''),
                service.get('is_injectable', True),
                service.get('provided_in')
            )
            self.counts['angular_services'] = self.counts.get('angular_services', 0) + 1

    def _store_angular_modules(self, file_path: str, angular_modules: list, jsx_pass: bool):
        """Store Angular module PARENT RECORDS ONLY.

        Junction data (declarations, imports, providers, exports) stored via dedicated handlers:
        - _store_angular_module_declarations()
        - _store_angular_module_imports()
        - _store_angular_module_providers()
        - _store_angular_module_exports()
        """
        for module in angular_modules:
            # NOTE: extractor returns 'name', we map to 'module_name'
            self.db_manager.add_angular_module(
                file_path,
                module.get('line', 0),
                module.get('name', '')
                # REMOVED: declarations, imports, providers, exports
                # Junction data now via dedicated handlers
            )
            self.counts['angular_modules'] = self.counts.get('angular_modules', 0) + 1

    def _store_angular_guards(self, file_path: str, angular_guards: list, jsx_pass: bool):
        """Store Angular guard definitions."""
        for guard in angular_guards:
            # NOTE: extractor returns 'name', we map to 'guard_name'
            self.db_manager.add_angular_guard(
                file_path,
                guard.get('line', 0),
                guard.get('name', ''),
                guard.get('guard_type', ''),
                guard.get('implements_interface')
            )
            self.counts['angular_guards'] = self.counts.get('angular_guards', 0) + 1

    def _store_di_injections(self, file_path: str, di_injections: list, jsx_pass: bool):
        """Store Dependency Injection patterns."""
        for injection in di_injections:
            # NOTE: extractor returns 'service', we map to 'injected_service'
            self.db_manager.add_di_injection(
                file_path,
                injection.get('line', 0),
                injection.get('target_class', ''),
                injection.get('service', ''),
                injection.get('injection_type', 'constructor')
            )
            self.counts['di_injections'] = self.counts.get('di_injections', 0) + 1

    def _store_lock_analysis(self, file_path: str, lock_analysis: list, jsx_pass: bool):
        """Store lock analysis."""
        for lock in lock_analysis:
            self.db_manager.add_lock_analysis(
                lock['file_path'],
                lock['lock_type'],
                lock.get('package_manager_version'),
                lock['total_packages'],
                lock.get('duplicate_packages'),
                lock.get('lock_file_version')
            )
            if 'lock_analysis' not in self.counts:
                self.counts['lock_analysis'] = 0
            self.counts['lock_analysis'] += 1

    def _store_import_styles(self, file_path: str, import_styles: list, jsx_pass: bool):
        """Store import styles."""
        for import_style in import_styles:
            self.db_manager.add_import_style(
                file_path,
                import_style['line'],
                import_style['package'],
                import_style['import_style'],
                import_style.get('imported_names'),
                import_style.get('alias_name'),
                import_style.get('full_statement')
            )
            if 'import_styles' not in self.counts:
                self.counts['import_styles'] = 0
            self.counts['import_styles'] += 1

    def _store_frontend_api_calls(self, file_path: str, frontend_api_calls: list, jsx_pass: bool):
        """Store frontend API calls (fetch/axios) for cross-boundary flow tracking."""
        for call in frontend_api_calls:
            self.db_manager.add_frontend_api_call(
                file_path,
                call['line'],
                call['method'],
                call['url_literal'],
                call.get('body_variable'),
                call.get('function_name')
            )
            if 'frontend_api_calls' not in self.counts:
                self.counts['frontend_api_calls'] = 0
            self.counts['frontend_api_calls'] += 1

    # =========================================================================
    # Vue Junction Array Handlers (normalize-node-extractor-output)
    # =========================================================================

    def _store_vue_component_props(self, file_path: str, vue_component_props: list, jsx_pass: bool):
        """Store Vue component props from flat junction array."""
        for prop in vue_component_props:
            self.db_manager.add_vue_component_prop(
                file_path,
                prop.get('component_name', ''),
                prop.get('prop_name', ''),
                prop.get('prop_type'),
                prop.get('is_required', 0),
                prop.get('default_value')
            )
            self.counts['vue_component_props'] = self.counts.get('vue_component_props', 0) + 1

    def _store_vue_component_emits(self, file_path: str, vue_component_emits: list, jsx_pass: bool):
        """Store Vue component emits from flat junction array."""
        for emit in vue_component_emits:
            self.db_manager.add_vue_component_emit(
                file_path,
                emit.get('component_name', ''),
                emit.get('emit_name', ''),
                emit.get('payload_type')
            )
            self.counts['vue_component_emits'] = self.counts.get('vue_component_emits', 0) + 1

    def _store_vue_component_setup_returns(self, file_path: str, vue_component_setup_returns: list, jsx_pass: bool):
        """Store Vue component setup returns from flat junction array."""
        for ret in vue_component_setup_returns:
            self.db_manager.add_vue_component_setup_return(
                file_path,
                ret.get('component_name', ''),
                ret.get('return_name', ''),
                ret.get('return_type')
            )
            self.counts['vue_component_setup_returns'] = self.counts.get('vue_component_setup_returns', 0) + 1

    # =========================================================================
    # Angular Junction Array Handlers (normalize-node-extractor-output)
    # =========================================================================

    def _store_angular_component_styles(self, file_path: str, angular_component_styles: list, jsx_pass: bool):
        """Store Angular component styles from flat junction array."""
        for style in angular_component_styles:
            self.db_manager.add_angular_component_style(
                file_path,
                style.get('component_name', ''),
                style.get('style_path', '')
            )
            self.counts['angular_component_styles'] = self.counts.get('angular_component_styles', 0) + 1

    def _store_angular_module_declarations(self, file_path: str, angular_module_declarations: list, jsx_pass: bool):
        """Store Angular module declarations from flat junction array."""
        for decl in angular_module_declarations:
            self.db_manager.add_angular_module_declaration(
                file_path,
                decl.get('module_name', ''),
                decl.get('declaration_name', ''),
                decl.get('declaration_type')
            )
            self.counts['angular_module_declarations'] = self.counts.get('angular_module_declarations', 0) + 1

    def _store_angular_module_imports(self, file_path: str, angular_module_imports: list, jsx_pass: bool):
        """Store Angular module imports from flat junction array."""
        for imp in angular_module_imports:
            self.db_manager.add_angular_module_import(
                file_path,
                imp.get('module_name', ''),
                imp.get('imported_module', '')
            )
            self.counts['angular_module_imports'] = self.counts.get('angular_module_imports', 0) + 1

    def _store_angular_module_providers(self, file_path: str, angular_module_providers: list, jsx_pass: bool):
        """Store Angular module providers from flat junction array."""
        for prov in angular_module_providers:
            self.db_manager.add_angular_module_provider(
                file_path,
                prov.get('module_name', ''),
                prov.get('provider_name', ''),
                prov.get('provider_type')
            )
            self.counts['angular_module_providers'] = self.counts.get('angular_module_providers', 0) + 1

    def _store_angular_module_exports(self, file_path: str, angular_module_exports: list, jsx_pass: bool):
        """Store Angular module exports from flat junction array."""
        for exp in angular_module_exports:
            self.db_manager.add_angular_module_export(
                file_path,
                exp.get('module_name', ''),
                exp.get('exported_name', '')
            )
            self.counts['angular_module_exports'] = self.counts.get('angular_module_exports', 0) + 1
