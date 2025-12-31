"""Command executor - HOP 12: Shell command execution.

This is the COMMAND INJECTION SINK. Tainted user input is
concatenated into shell commands and executed.
"""

import subprocess
import os

from app.utils.string_utils import clean_whitespace


class CommandExecutor:
    """Shell command executor.

    HOP 12: Executes shell commands with user-controlled input.

    VULNERABILITY: Command Injection - User input in shell commands.
    """

    def __init__(self):
        self.temp_dir = "/tmp/reports"

    def convert_format(self, content: str, output_format: str) -> dict:
        """Convert content to specified format.

        COMMAND INJECTION SINK.

        Args:
            content: Content to convert
            output_format: TAINTED format string

        VULNERABILITY: shell=True with user input allows command injection.
        Payload: pdf; rm -rf / #
        """
        # Create temp file
        temp_file = f"{self.temp_dir}/report.html"
        output_file = f"{self.temp_dir}/report.{output_format}"

        # Write content to temp file
        os.makedirs(self.temp_dir, exist_ok=True)
        with open(temp_file, "w") as f:
            f.write(content)

        # VULNERABLE: shell=True with user-controlled format
        # User can inject commands via output_format
        output_format = clean_whitespace(output_format)  # Still TAINTED
        cmd = f"wkhtmltopdf {temp_file} {output_file} --format {output_format}"

        try:
            result = subprocess.run(
                cmd,
                shell=True,  # VULNERABLE: shell=True
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "status": "converted",
                "output": output_file,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"error": str(e)}

    def export(self, report_id: str, output_format: str) -> dict:
        """Export report to specified format.

        COMMAND INJECTION SINK.

        Args:
            report_id: Report ID
            output_format: TAINTED format - command injection vector
        """
        # VULNERABLE: User-controlled format in command
        cmd = f"report-exporter --id {report_id} --format {output_format}"

        try:
            result = subprocess.run(
                cmd,
                shell=True,  # COMMAND INJECTION SINK
                capture_output=True,
                text=True,
            )
            return {"status": "exported", "returncode": result.returncode}
        except Exception as e:
            return {"error": str(e)}

    def run_script(self, script_name: str, args: str) -> dict:
        """Run a script with arguments.

        COMMAND INJECTION SINK.

        Args:
            script_name: Script to run
            args: TAINTED arguments - command injection vector
        """
        # VULNERABLE: User-controlled arguments
        cmd = f"./scripts/{script_name} {args}"

        try:
            result = subprocess.run(
                cmd,
                shell=True,  # COMMAND INJECTION SINK
                capture_output=True,
                text=True,
            )
            return {"output": result.stdout, "errors": result.stderr}
        except Exception as e:
            return {"error": str(e)}
