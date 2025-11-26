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
            'sequelize_models': self._store_sequelize_models,
            'sequelize_associations': self._store_sequelize_associations,
            'bullmq_queues': self._store_bullmq_queues,
            'bullmq_workers': self._store_bullmq_workers,
            'angular_components': self._store_angular_components,
            'angular_services': self._store_angular_services,
            'angular_modules': self._store_angular_modules,
            'angular_guards': self._store_angular_guards,
            'di_injections': self._store_di_injections,
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
        """Store Vue-specific data."""
        for component in vue_components:
            self.db_manager.add_vue_component(
                file_path,
                component['name'],
                component['type'],
                component['start_line'],
                component['end_line'],
                component.get('has_template', False),
                component.get('has_style', False),
                component.get('composition_api_used', False),
                component.get('props_definition'),
                component.get('emits_definition'),
                component.get('setup_return')
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
        cursor = self.db_manager.conn.cursor()
        for model in sequelize_models:
            # Handle both dict and string formats
            if isinstance(model, str):
                # If it's a string, create a basic dict with the model name
                model_data = {'model_name': model, 'line': 0}
            else:
                model_data = model

            cursor.execute("""
                INSERT OR REPLACE INTO sequelize_models
                (file, line, model_name, table_name, extends_model)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                model_data.get('line', 0),
                model_data.get('model_name', ''),
                model_data.get('table_name'),  # Can be None
                model_data.get('extends_model', False)
            ))
            if 'sequelize_models' not in self.counts:
                self.counts['sequelize_models'] = 0
            self.counts['sequelize_models'] += 1

    def _store_sequelize_associations(self, file_path: str, sequelize_associations: list, jsx_pass: bool):
        """Store Sequelize model associations."""
        cursor = self.db_manager.conn.cursor()
        for assoc in sequelize_associations:
            cursor.execute("""
                INSERT OR REPLACE INTO sequelize_associations
                (file, line, model_name, association_type, target_model, foreign_key, through_table)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                assoc.get('line', 0),
                assoc.get('model_name', ''),
                assoc.get('association_type', ''),
                assoc.get('target_model', ''),
                assoc.get('foreign_key'),  # Can be None
                assoc.get('through_table')  # Can be None
            ))
            if 'sequelize_associations' not in self.counts:
                self.counts['sequelize_associations'] = 0
            self.counts['sequelize_associations'] += 1

    def _store_bullmq_queues(self, file_path: str, bullmq_queues: list, jsx_pass: bool):
        """Store BullMQ queue definitions."""
        cursor = self.db_manager.conn.cursor()
        for queue in bullmq_queues:
            cursor.execute("""
                INSERT OR REPLACE INTO bullmq_queues
                (file, line, queue_name, redis_config)
                VALUES (?, ?, ?, ?)
            """, (
                file_path,
                queue.get('line', 0),
                queue.get('name', ''),  # NOTE: extractor returns 'name', we map to 'queue_name'
                queue.get('redis_config')
            ))
            if 'bullmq_queues' not in self.counts:
                self.counts['bullmq_queues'] = 0
            self.counts['bullmq_queues'] += 1

    def _store_bullmq_workers(self, file_path: str, bullmq_workers: list, jsx_pass: bool):
        """Store BullMQ worker definitions."""
        cursor = self.db_manager.conn.cursor()
        for worker in bullmq_workers:
            cursor.execute("""
                INSERT OR REPLACE INTO bullmq_workers
                (file, line, queue_name, worker_function, processor_path)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                worker.get('line', 0),
                worker.get('queue_name', ''),
                worker.get('worker_function'),
                worker.get('processor_path')
            ))
            if 'bullmq_workers' not in self.counts:
                self.counts['bullmq_workers'] = 0
            self.counts['bullmq_workers'] += 1

    def _store_angular_components(self, file_path: str, angular_components: list, jsx_pass: bool):
        """Store Angular component definitions."""
        cursor = self.db_manager.conn.cursor()
        for component in angular_components:
            cursor.execute("""
                INSERT OR REPLACE INTO angular_components
                (file, line, component_name, selector, template_path, style_paths, has_lifecycle_hooks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                component.get('line', 0),
                component.get('name', ''),
                component.get('selector'),
                component.get('template_path'),
                component.get('style_paths'),  # Already stringified by extractor
                component.get('has_lifecycle_hooks', False)
            ))
            if 'angular_components' not in self.counts:
                self.counts['angular_components'] = 0
            self.counts['angular_components'] += 1

    def _store_angular_services(self, file_path: str, angular_services: list, jsx_pass: bool):
        """Store Angular service definitions."""
        cursor = self.db_manager.conn.cursor()
        for service in angular_services:
            cursor.execute("""
                INSERT OR REPLACE INTO angular_services
                (file, line, service_name, is_injectable, provided_in)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                service.get('line', 0),
                service.get('name', ''),
                service.get('is_injectable', True),
                service.get('provided_in')
            ))
            if 'angular_services' not in self.counts:
                self.counts['angular_services'] = 0
            self.counts['angular_services'] += 1

    def _store_angular_modules(self, file_path: str, angular_modules: list, jsx_pass: bool):
        """Store Angular module definitions."""
        cursor = self.db_manager.conn.cursor()
        for module in angular_modules:
            cursor.execute("""
                INSERT OR REPLACE INTO angular_modules
                (file, line, module_name, declarations, imports, providers, exports)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                module.get('line', 0),
                module.get('name', ''),
                module.get('declarations'),  # Already stringified
                module.get('imports'),
                module.get('providers'),
                module.get('exports')
            ))
            if 'angular_modules' not in self.counts:
                self.counts['angular_modules'] = 0
            self.counts['angular_modules'] += 1

    def _store_angular_guards(self, file_path: str, angular_guards: list, jsx_pass: bool):
        """Store Angular guard definitions."""
        cursor = self.db_manager.conn.cursor()
        for guard in angular_guards:
            cursor.execute("""
                INSERT OR REPLACE INTO angular_guards
                (file, line, guard_name, guard_type, implements_interface)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                guard.get('line', 0),
                guard.get('name', ''),
                guard.get('guard_type', ''),
                guard.get('implements_interface')
            ))
            if 'angular_guards' not in self.counts:
                self.counts['angular_guards'] = 0
            self.counts['angular_guards'] += 1

    def _store_di_injections(self, file_path: str, di_injections: list, jsx_pass: bool):
        """Store Dependency Injection patterns."""
        cursor = self.db_manager.conn.cursor()
        for injection in di_injections:
            cursor.execute("""
                INSERT OR REPLACE INTO di_injections
                (file, line, target_class, injected_service, injection_type)
                VALUES (?, ?, ?, ?, ?)
            """, (
                file_path,
                injection.get('line', 0),
                injection.get('target_class', ''),
                injection.get('service', ''),  # NOTE: extractor returns 'service', map to 'injected_service'
                injection.get('injection_type', 'constructor')
            ))
            if 'di_injections' not in self.counts:
                self.counts['di_injections'] = 0
            self.counts['di_injections'] += 1

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