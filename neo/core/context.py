"""Runtime execution context tracking data across workflow steps."""

import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RunContext(BaseModel):
    """Stores execution state and data passing between steps."""
    trigger: Dict[str, Any] = Field(default_factory=dict)
    steps: Dict[str, Any] = Field(default_factory=dict)
    env: Dict[str, str] = Field(default_factory=lambda: dict(os.environ))
    vars: Dict[str, Any] = Field(default_factory=dict)

    def set_step_data(self, step_id: str, data: Any) -> None:
        """Stores output from a completed step."""
        self.steps[step_id] = data

    def get_template_scope(self) -> Dict[str, Any]:
        """Provides the variable scope available inside Jinja2 expressions."""
        # Allow both steps.trigger.* and trigger.* access
        step_scope = {"trigger": self.trigger}
        step_scope.update(self.steps)

        return {
            "trigger": self.trigger,
            "steps": step_scope,
            "env": self.env,
            "vars": self.vars
        }
