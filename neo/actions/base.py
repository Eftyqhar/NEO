"""Abstract base class for all Neo action and transformer nodes."""

from abc import ABC, abstractmethod
from typing import Any
from neo.core.models import StepConfig
from neo.core.context import RunContext
from neo.core.templating import TemplateEngine


class BaseAction(ABC):
    """Base class for all action nodes (SMTP, Telegram, HTTP, Shell, etc.)."""

    def __init__(self, templater: TemplateEngine = None):
        self.templater = templater or TemplateEngine()

    @abstractmethod
    async def execute(self, step: StepConfig, context: RunContext) -> Any:
        """Executes the action and returns result data to be stored in context.steps[step.id]."""
        pass
