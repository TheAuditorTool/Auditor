"""GitHub Actions workflow extractor - Fidelity-Compliant Architecture."""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from theauditor.utils.logging import logger

from ..fidelity_utils import FidelityToken
from . import BaseExtractor


class GitHubWorkflowExtractor(BaseExtractor):
    """Extractor for GitHub Actions workflow files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return [".yml", ".yaml"]

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file."""
        path_normalized = Path(file_path).as_posix().lower()
        return ".github/workflows/" in path_normalized

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract GitHub Actions workflow data and return with fidelity manifest."""
        workflow_path = str(file_info["path"])

        result = {
            "github_workflows": [],
            "github_jobs": [],
            "github_steps": [],
            "github_step_outputs": [],
            "github_step_references": [],
            "github_job_dependencies": [],
        }

        try:
            workflow_data = yaml.safe_load(content)
            if not workflow_data or not isinstance(workflow_data, dict):
                return FidelityToken.attach_manifest(result)

            workflow_record = self._extract_workflow(workflow_path, workflow_data)
            result["github_workflows"].append(workflow_record)

            jobs_data = workflow_data.get("jobs", {})
            if isinstance(jobs_data, dict):
                jobs, job_deps, steps, step_outputs, step_refs = self._extract_jobs(
                    workflow_path, jobs_data
                )
                result["github_jobs"].extend(jobs)
                result["github_job_dependencies"].extend(job_deps)
                result["github_steps"].extend(steps)
                result["github_step_outputs"].extend(step_outputs)
                result["github_step_references"].extend(step_refs)

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse workflow {workflow_path}: {e}")
            return FidelityToken.attach_manifest(result)
        except Exception as e:
            logger.error(f"Failed to extract workflow {workflow_path}: {e}")
            return FidelityToken.attach_manifest(result)

        return FidelityToken.attach_manifest(result)

    def _extract_workflow(self, workflow_path: str, workflow_data: dict) -> dict:
        """Extract workflow-level metadata and return as dict."""
        workflow_name = workflow_data.get("name")
        if not workflow_name:
            workflow_name = Path(workflow_path).stem

        on_triggers = workflow_data.get("on") or workflow_data.get(True) or []
        if isinstance(on_triggers, str):
            on_triggers_json = json.dumps([on_triggers])
        elif isinstance(on_triggers, list):
            on_triggers_json = json.dumps(on_triggers)
        elif isinstance(on_triggers, dict):
            on_triggers_json = json.dumps(list(on_triggers.keys()))
        else:
            on_triggers_json = json.dumps([])

        permissions = workflow_data.get("permissions")
        permissions_json = json.dumps(permissions) if permissions else None

        concurrency = workflow_data.get("concurrency")
        concurrency_json = json.dumps(concurrency) if concurrency else None

        env = workflow_data.get("env")
        env_json = json.dumps(env) if env else None

        return {
            "workflow_path": workflow_path,
            "workflow_name": workflow_name,
            "on_triggers": on_triggers_json,
            "permissions": permissions_json,
            "concurrency": concurrency_json,
            "env": env_json,
        }

    def _extract_jobs(
        self, workflow_path: str, jobs_data: dict
    ) -> tuple[list, list, list, list, list]:
        """Extract jobs and their steps, returning data lists."""
        jobs = []
        job_dependencies = []
        all_steps = []
        all_step_outputs = []
        all_step_references = []

        for job_key, job_value in jobs_data.items():
            if not isinstance(job_value, dict):
                continue

            job_id = f"{workflow_path}::{job_key}"

            job_name = job_value.get("name")

            runs_on = job_value.get("runs-on")
            if isinstance(runs_on, str):
                runs_on_json = json.dumps([runs_on])
            elif isinstance(runs_on, list):
                runs_on_json = json.dumps(runs_on)
            else:
                runs_on_json = None

            strategy = job_value.get("strategy")
            strategy_json = json.dumps(strategy) if strategy else None

            permissions = job_value.get("permissions")
            permissions_json = json.dumps(permissions) if permissions else None

            env = job_value.get("env")
            env_json = json.dumps(env) if env else None

            if_condition = job_value.get("if")

            timeout_minutes = job_value.get("timeout-minutes")

            uses_reusable = "uses" in job_value
            reusable_path = job_value.get("uses") if uses_reusable else None

            jobs.append(
                {
                    "job_id": job_id,
                    "workflow_path": workflow_path,
                    "job_key": job_key,
                    "job_name": job_name,
                    "runs_on": runs_on_json,
                    "strategy": strategy_json,
                    "permissions": permissions_json,
                    "env": env_json,
                    "if_condition": if_condition,
                    "timeout_minutes": timeout_minutes,
                    "uses_reusable_workflow": uses_reusable,
                    "reusable_workflow_path": reusable_path,
                }
            )

            needs = job_value.get("needs", [])
            if isinstance(needs, str):
                needs_list = [needs]
            elif isinstance(needs, list):
                needs_list = needs
            else:
                needs_list = []

            for needed_job_key in needs_list:
                needed_job_id = f"{workflow_path}::{needed_job_key}"
                job_dependencies.append(
                    {
                        "job_id": job_id,
                        "needs_job_id": needed_job_id,
                    }
                )

            steps = job_value.get("steps", [])
            if isinstance(steps, list):
                step_list, output_list, ref_list = self._extract_steps(job_id, steps)
                all_steps.extend(step_list)
                all_step_outputs.extend(output_list)
                all_step_references.extend(ref_list)

        return jobs, job_dependencies, all_steps, all_step_outputs, all_step_references

    def _extract_steps(self, job_id: str, steps: list[dict]) -> tuple[list, list, list]:
        """Extract steps and their references, returning data lists."""
        step_list = []
        output_list = []
        reference_list = []

        for sequence_order, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            step_id = f"{job_id}::{sequence_order}"

            step_name = step.get("name")

            uses_action = step.get("uses")
            uses_version = None
            if uses_action and "@" in uses_action:
                action_parts = uses_action.split("@", 1)
                uses_action = action_parts[0]
                uses_version = action_parts[1]

            run_script = step.get("run")

            shell = step.get("shell")

            env = step.get("env")
            env_json = json.dumps(env) if env else None

            with_args = step.get("with")
            with_args_json = json.dumps(with_args) if with_args else None

            if_condition = step.get("if")

            timeout_minutes = step.get("timeout-minutes")

            continue_on_error = step.get("continue-on-error", False)

            step_list.append(
                {
                    "step_id": step_id,
                    "job_id": job_id,
                    "sequence_order": sequence_order,
                    "step_name": step_name,
                    "uses_action": uses_action,
                    "uses_version": uses_version,
                    "run_script": run_script,
                    "shell": shell,
                    "env": env_json,
                    "with_args": with_args_json,
                    "if_condition": if_condition,
                    "timeout_minutes": timeout_minutes,
                    "continue_on_error": continue_on_error,
                }
            )

            outputs = step.get("outputs")
            if isinstance(outputs, dict):
                for output_name, output_expr in outputs.items():
                    output_list.append(
                        {
                            "step_id": step_id,
                            "output_name": output_name,
                            "output_expression": str(output_expr),
                        }
                    )

            reference_list.extend(self._extract_references(step_id, "run", run_script))
            reference_list.extend(self._extract_references(step_id, "if", if_condition))
            if env:
                for _env_key, env_value in env.items():
                    reference_list.extend(self._extract_references(step_id, "env", str(env_value)))
            if with_args:
                for _with_key, with_value in with_args.items():
                    reference_list.extend(
                        self._extract_references(step_id, "with", str(with_value))
                    )

        return step_list, output_list, reference_list

    def _extract_references(self, step_id: str, location: str, text: str | None) -> list[dict]:
        """Extract ${{ }} expression references from text, returning list of dicts."""
        if not text:
            return []

        references = []
        pattern = r"\$\{\{\s*([^}]+)\s*\}\}"
        matches = re.findall(pattern, text)

        for match in matches:
            reference_path = match.strip()

            first_segment = reference_path.split(".")[0].split("[")[0]
            reference_type = first_segment

            references.append(
                {
                    "step_id": step_id,
                    "reference_location": location,
                    "reference_type": reference_type,
                    "reference_path": reference_path,
                }
            )

        return references
