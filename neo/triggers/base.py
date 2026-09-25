"""Abstract base class for all Neo event triggers."""

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict
from neo.core.models import TriggerConfig
from neo.core.templating import TemplateEngine


class BaseTrigger(ABC):
    """Base class for all real-time event listeners (IMAP IDLE, Telegram, Webhook, etc.)."""

    def __init__(self, config: TriggerConfig, templater: TemplateEngine = None):
        self.config = config
        self.templater = templater or TemplateEngine()
        self.is_running = False

    @abstractmethod
    async def start(self, on_event: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Starts the real-time listener loop and dispatches payloads to on_event."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully terminates the listener connection."""
        pass
