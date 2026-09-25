"""Shell command execution action node."""

import asyncio
import os
import sys
from typing import Any, Dict

from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


class ExecAction(BaseAction):
    """Executes a shell command asynchronously and captures its output."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        command = resolved.get("command") or resolved.get("cmd")
        if not command:
            raise ValueError(f"Step '{step.id}' (exec) missing required 'command' parameter.")

        cwd = resolved.get("cwd", os.getcwd())
        timeout = float(resolved.get("timeout", 60.0))

        # Windows vs Unix shell handling
        if sys.platform == "win32":
            # Prefer PowerShell if available, fallback to cmd.exe
            shell_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            shell_cmd = ["/bin/bash", "-c", command]

        process = await asyncio.create_subprocess_exec(
            *shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(f"Step '{step.id}' timed out after {timeout} seconds.")

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        exit_code = process.returncode

        if exit_code != 0 and not step.continue_on_error:
            raise RuntimeError(f"Command failed with exit code {exit_code}: {stderr or stdout}")

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "ok": exit_code == 0
        }
