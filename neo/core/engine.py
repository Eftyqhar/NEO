"""Asynchronous Workflow DAG and step execution engine."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from neo.core.context import RunContext
from neo.core.models import RunResult, StepConfig, StepResult, WorkflowConfig
from neo.core.templating import TemplateEngine
from neo.actions.base import BaseAction
from neo.actions.http_action import HttpAction
from neo.actions.exec_action import ExecAction
from neo.actions.smtp_action import SmtpAction
from neo.actions.telegram_action import TelegramAction
from neo.actions.filter_action import FilterAction, FilterStopException
from neo.actions.ai_action import AiAction


class WorkflowEngine:
    """Orchestrates step execution, context passing, and lifecycle events."""

    def __init__(self, templater: Optional[TemplateEngine] = None):
        self.templater = templater or TemplateEngine()
        self.actions: Dict[str, BaseAction] = {
            "http": HttpAction(self.templater),
            "exec": ExecAction(self.templater),
            "smtp": SmtpAction(self.templater),
            "telegram": TelegramAction(self.templater),
            "filter": FilterAction(self.templater),
            "ai": AiAction(self.templater),
        }

    def register_action(self, action_type: str, action: BaseAction) -> None:
        """Allows registering custom action nodes."""
        self.actions[action_type.lower()] = action

    async def execute(self, workflow: WorkflowConfig, trigger_data: Dict[str, Any]) -> RunResult:
        """Executes a workflow pipeline against an incoming trigger payload."""
        run_start = time.perf_counter()
        result = RunResult(
            workflow_name=workflow.name,
            trigger_type=workflow.trigger.type,
            trigger_data=trigger_data,
            started_at=datetime.now(timezone.utc)
        )

        context = RunContext(trigger=trigger_data)

        for step in workflow.steps:
            step_start = time.perf_counter()
            action_handler = self.actions.get(step.type.lower())

            if not action_handler:
                err_msg = f"Unknown action node type '{step.type}' in step '{step.id}'."
                result.steps[step.id] = StepResult(
                    step_id=step.id,
                    status="failed",
                    error=err_msg,
                    duration_ms=(time.perf_counter() - step_start) * 1000
                )
                result.status = "failed"
                result.error = err_msg
                break

            # Check step condition (for non-filter steps, false condition skips the single step)
            if step.condition and step.type.lower() != "filter":
                try:
                    should_run = self.templater.evaluate_condition(step.condition, context)
                    if not should_run:
                        result.steps[step.id] = StepResult(
                            step_id=step.id,
                            status="skipped",
                            data={"reason": f"Condition '{step.condition}' evaluated to False."},
                            duration_ms=(time.perf_counter() - step_start) * 1000
                        )
                        continue
                except Exception as cond_err:
                    err_msg = f"Condition error in step '{step.id}': {cond_err}"
                    result.steps[step.id] = StepResult(
                        step_id=step.id,
                        status="failed",
                        error=err_msg,
                        duration_ms=(time.perf_counter() - step_start) * 1000
                    )
                    result.status = "failed"
                    result.error = err_msg
                    break

            # Execute the step
            try:
                output_data = await action_handler.execute(step, context)
                step_duration = (time.perf_counter() - step_start) * 1000
                context.set_step_data(step.id, output_data)

                result.steps[step.id] = StepResult(
                    step_id=step.id,
                    status="success",
                    data=output_data,
                    duration_ms=step_duration
                )

            except FilterStopException as filter_stop:
                # Filter gracefully halted execution
                step_duration = (time.perf_counter() - step_start) * 1000
                result.steps[step.id] = StepResult(
                    step_id=step.id,
                    status="filtered",
                    data={"stopped": True, "message": str(filter_stop)},
                    duration_ms=step_duration
                )
                result.status = "success"
                break

            except Exception as e:
                step_duration = (time.perf_counter() - step_start) * 1000
                result.steps[step.id] = StepResult(
                    step_id=step.id,
                    status="failed",
                    error=str(e),
                    duration_ms=step_duration
                )

                if not step.continue_on_error:
                    result.status = "failed"
                    result.error = f"Step '{step.id}' failed: {e}"
                    break

        if result.status == "pending":
            result.status = "success"

        result.duration_ms = (time.perf_counter() - run_start) * 1000
        result.completed_at = datetime.now(timezone.utc)
        return result
