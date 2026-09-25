"""Filter and conditional branching action node."""

from typing import Any, Dict
from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


class FilterStopException(Exception):
    """Raised when a filter step condition evaluates to false, terminating pipeline."""
    pass


class FilterAction(BaseAction):
    """Evaluates a condition and halts the remaining pipeline if false."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        condition = resolved.get("condition") or resolved.get("expr")
        if not condition:
            return {"passed": True}

        passed = self.templater.evaluate_condition(condition, context)

        if not passed:
            raise FilterStopException(f"Pipeline stopped: condition '{condition}' evaluated to False.")

        return {"passed": True, "condition": condition}
