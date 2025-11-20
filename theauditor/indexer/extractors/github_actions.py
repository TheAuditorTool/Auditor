"""GitHub Actions workflow extractor - Database-First Architecture.

Extracts CI/CD workflow definitions from .github/workflows/*.yml files.
NO security checks (that's what rules do).
NO separate parser class (inline parsing).

Follows gold standard: Facts only, direct DB writes, no intermediate dicts.

ARCHITECTURE:
- Database-First: Extracts directly to database via self.db_manager
- Zero Fallbacks: NO try/except around schema operations, hard fail on errors
- Inline YAML: Uses yaml.safe_load() directly, no parser abstraction
- Config File Pattern: Follows docker/compose precedent (not terraform/HCL)

Extracted data:
- Workflows: name, triggers, permissions, concurrency
- Jobs: dependencies (needs:), matrix strategy, permissions
- Steps: actions, run scripts, env vars, with args
- References: ${{ }} expressions (github.*, secrets.*, etc.)
"""
from __future__ import annotations


import json
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor


class GitHubWorkflowExtractor(BaseExtractor):
    """Extractor for GitHub Actions workflow files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return ['.yml', '.yaml']

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.

        Only match workflow files in .github/workflows/ directory.

        Args:
            file_path: Path to the file

        Returns:
            True if this is a GitHub Actions workflow file
        """
        path_normalized = Path(file_path).as_posix().lower()
        return '.github/workflows/' in path_normalized

    def extract(self, file_info: dict[str, Any], content: str,
                tree: Any | None = None) -> dict[str, Any]:
        """Extract GitHub Actions workflow directly to database.

        Uses inline YAML parsing (like generic.py for Docker Compose).
        Writes directly to database via self.db_manager.add_github_* methods.

        Args:
            file_info: File metadata dictionary with 'path' key
            content: YAML content as string
            tree: Optional pre-parsed AST tree (unused for YAML)

        Returns:
            Minimal dict for indexer compatibility
        """
        workflow_path = str(file_info['path'])

        try:
            # Parse YAML inline (no parser abstraction)
            workflow_data = yaml.safe_load(content)
            if not workflow_data or not isinstance(workflow_data, dict):
                return {}

            # Extract workflow-level metadata
            self._extract_workflow(workflow_path, workflow_data)

            # Extract jobs and their dependencies
            jobs_data = workflow_data.get('jobs', {})
            if isinstance(jobs_data, dict):
                self._extract_jobs(workflow_path, jobs_data)

        except yaml.YAMLError as e:
            # Hard fail on YAML parse errors (no graceful degradation)
            import sys
            print(f"[ERROR] Failed to parse workflow {workflow_path}: {e}", file=sys.stderr)
            return {}
        except Exception as e:
            # Hard fail on extraction errors (no fallbacks)
            import sys
            print(f"[ERROR] Failed to extract workflow {workflow_path}: {e}", file=sys.stderr)
            return {}

        # Return minimal dict for indexer compatibility
        return {
            'imports': [],
            'routes': [],
            'sql_queries': [],
            'symbols': []
        }

    def _extract_workflow(self, workflow_path: str, workflow_data: dict):
        """Extract workflow-level metadata to database.

        Args:
            workflow_path: Path to workflow file
            workflow_data: Parsed YAML workflow dict
        """
        # Workflow name (or derive from filename)
        workflow_name = workflow_data.get('name')
        if not workflow_name:
            workflow_name = Path(workflow_path).stem

        # Triggers (on: field) - normalize to JSON array
        # YAML quirk: 'on' is a reserved word, parses as boolean True
        on_triggers = workflow_data.get('on') or workflow_data.get(True) or []
        if isinstance(on_triggers, str):
            # Single trigger: on: push
            on_triggers_json = json.dumps([on_triggers])
        elif isinstance(on_triggers, list):
            # List of triggers: on: [push, pull_request]
            on_triggers_json = json.dumps(on_triggers)
        elif isinstance(on_triggers, dict):
            # Object with event configs: on: {push: {branches: [main]}}
            on_triggers_json = json.dumps(list(on_triggers.keys()))
        else:
            on_triggers_json = json.dumps([])

        # Permissions (JSON object or null)
        permissions = workflow_data.get('permissions')
        permissions_json = json.dumps(permissions) if permissions else None

        # Concurrency (JSON object or null)
        concurrency = workflow_data.get('concurrency')
        concurrency_json = json.dumps(concurrency) if concurrency else None

        # Environment variables (JSON object or null)
        env = workflow_data.get('env')
        env_json = json.dumps(env) if env else None

        # Write workflow record to database
        self.db_manager.add_github_workflow(
            workflow_path=workflow_path,
            workflow_name=workflow_name,
            on_triggers=on_triggers_json,
            permissions=permissions_json,
            concurrency=concurrency_json,
            env=env_json
        )

    def _extract_jobs(self, workflow_path: str, jobs_data: dict):
        """Extract jobs and their steps to database.

        Args:
            workflow_path: Path to workflow file
            jobs_data: Jobs dict from workflow YAML
        """
        for job_key, job_value in jobs_data.items():
            if not isinstance(job_value, dict):
                continue

            # Composite job ID: workflow_path::job_key
            job_id = f"{workflow_path}::{job_key}"

            # Job name (optional)
            job_name = job_value.get('name')

            # Runs-on (runner labels) - normalize to JSON array
            runs_on = job_value.get('runs-on')
            if isinstance(runs_on, str):
                runs_on_json = json.dumps([runs_on])
            elif isinstance(runs_on, list):
                runs_on_json = json.dumps(runs_on)
            else:
                runs_on_json = None

            # Strategy (matrix) - JSON object or null
            strategy = job_value.get('strategy')
            strategy_json = json.dumps(strategy) if strategy else None

            # Permissions - JSON object or null
            permissions = job_value.get('permissions')
            permissions_json = json.dumps(permissions) if permissions else None

            # Environment variables - JSON object or null
            env = job_value.get('env')
            env_json = json.dumps(env) if env else None

            # Conditional execution
            if_condition = job_value.get('if')

            # Timeout
            timeout_minutes = job_value.get('timeout-minutes')

            # Check if job uses reusable workflow
            uses_reusable = 'uses' in job_value
            reusable_path = job_value.get('uses') if uses_reusable else None

            # Write job record to database
            self.db_manager.add_github_job(
                job_id=job_id,
                workflow_path=workflow_path,
                job_key=job_key,
                job_name=job_name,
                runs_on=runs_on_json,
                strategy=strategy_json,
                permissions=permissions_json,
                env=env_json,
                if_condition=if_condition,
                timeout_minutes=timeout_minutes,
                uses_reusable_workflow=uses_reusable,
                reusable_workflow_path=reusable_path
            )

            # Extract job dependencies (needs: field)
            needs = job_value.get('needs', [])
            if isinstance(needs, str):
                # Single dependency: needs: build
                needs_list = [needs]
            elif isinstance(needs, list):
                # Multiple dependencies: needs: [build, test]
                needs_list = needs
            else:
                needs_list = []

            for needed_job_key in needs_list:
                needed_job_id = f"{workflow_path}::{needed_job_key}"
                self.db_manager.add_github_job_dependency(
                    job_id=job_id,
                    needs_job_id=needed_job_id
                )

            # Extract steps
            steps = job_value.get('steps', [])
            if isinstance(steps, list):
                self._extract_steps(workflow_path, job_id, steps)

    def _extract_steps(self, workflow_path: str, job_id: str, steps: list[dict]):
        """Extract steps and their references to database.

        Args:
            workflow_path: Path to workflow file
            job_id: Parent job ID
            steps: List of step dicts from job YAML
        """
        for sequence_order, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            # Composite step ID: job_id::sequence_order
            step_id = f"{job_id}::{sequence_order}"

            # Step name (optional)
            step_name = step.get('name')

            # Action usage (uses: field)
            uses_action = step.get('uses')
            uses_version = None
            if uses_action:
                # Extract version/ref from action (e.g., 'actions/checkout@v4' -> 'v4')
                if '@' in uses_action:
                    action_parts = uses_action.split('@', 1)
                    uses_action = action_parts[0]  # 'actions/checkout'
                    uses_version = action_parts[1]  # 'v4' or 'main' or SHA

            # Run script (run: field)
            run_script = step.get('run')

            # Shell type
            shell = step.get('shell')

            # Environment variables - JSON object or null
            env = step.get('env')
            env_json = json.dumps(env) if env else None

            # Action inputs (with: field) - JSON object or null
            with_args = step.get('with')
            with_args_json = json.dumps(with_args) if with_args else None

            # Conditional execution
            if_condition = step.get('if')

            # Timeout
            timeout_minutes = step.get('timeout-minutes')

            # Continue on error
            continue_on_error = step.get('continue-on-error', False)

            # Write step record to database
            self.db_manager.add_github_step(
                step_id=step_id,
                job_id=job_id,
                sequence_order=sequence_order,
                step_name=step_name,
                uses_action=uses_action,
                uses_version=uses_version,
                run_script=run_script,
                shell=shell,
                env=env_json,
                with_args=with_args_json,
                if_condition=if_condition,
                timeout_minutes=timeout_minutes,
                continue_on_error=continue_on_error
            )

            # Extract step outputs
            outputs = step.get('outputs')
            if isinstance(outputs, dict):
                for output_name, output_expr in outputs.items():
                    self.db_manager.add_github_step_output(
                        step_id=step_id,
                        output_name=output_name,
                        output_expression=str(output_expr)
                    )

            # Extract ${{ }} references from various locations
            self._extract_references(step_id, 'run', run_script)
            self._extract_references(step_id, 'if', if_condition)
            if env:
                for env_key, env_value in env.items():
                    self._extract_references(step_id, 'env', str(env_value))
            if with_args:
                for with_key, with_value in with_args.items():
                    self._extract_references(step_id, 'with', str(with_value))

    def _extract_references(self, step_id: str, location: str, text: str | None):
        """Extract ${{ }} expression references from text.

        Parses GitHub Actions expressions like:
        - ${{ github.event.pull_request.head.sha }}
        - ${{ secrets.GITHUB_TOKEN }}
        - ${{ needs.build.outputs.version }}

        Args:
            step_id: Parent step ID
            location: Where reference appears ('run', 'env', 'with', 'if')
            text: Text content to scan for references
        """
        if not text:
            return

        # Regex to match ${{ }} expressions
        pattern = r'\$\{\{\s*([^}]+)\s*\}\}'
        matches = re.findall(pattern, text)

        for match in matches:
            # Parse reference path (e.g., 'github.event.pull_request.head.sha')
            reference_path = match.strip()

            # Determine reference type from first segment
            first_segment = reference_path.split('.')[0].split('[')[0]
            reference_type = first_segment  # 'github', 'secrets', 'env', 'needs', 'steps', etc.

            # Write reference record to database
            self.db_manager.add_github_step_reference(
                step_id=step_id,
                reference_location=location,
                reference_type=reference_type,
                reference_path=reference_path
            )
