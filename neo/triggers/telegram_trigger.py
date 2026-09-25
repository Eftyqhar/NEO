"""Real-time Telegram Bot event listener using async long-polling."""

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional
import httpx

from neo.triggers.base import BaseTrigger
from neo.core.models import TriggerConfig
from neo.core.context import RunContext


class TelegramTrigger(BaseTrigger):
    """Listens for Telegram Bot messages and commands in real time."""

    def __init__(self, config: TriggerConfig, templater=None):
        super().__init__(config, templater)
        self._task: Optional[asyncio.Task] = None

    async def start(self, on_event: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self.is_running = True
        context = RunContext()
        cfg = self.templater.resolve(self.config.model_dump(), context)

        bot_token = cfg.get("bot_token") or cfg.get("token")
        if not bot_token:
            raise ValueError("Telegram trigger requires 'bot_token'.")

        expected_command = cfg.get("command")
        chat_id_filter = cfg.get("chat_id")

        self._task = asyncio.create_task(
            self._polling_loop(bot_token, expected_command, chat_id_filter, on_event)
        )

    async def _polling_loop(
        self, bot_token: str, expected_command: Optional[str],
        chat_id_filter: Optional[Any], on_event: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        offset = 0
        api_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

        async with httpx.AsyncClient(timeout=45.0) as client:
            while self.is_running:
                try:
                    params = {"offset": offset, "timeout": 30}
                    resp = await client.get(api_url, params=params)

                    if not resp.is_success:
                        await asyncio.sleep(3)
                        continue

                    data = resp.json()
                    if not data.get("ok"):
                        await asyncio.sleep(3)
                        continue

                    updates = data.get("result", [])
                    for update in updates:
                        offset = update["update_id"] + 1
                        message = update.get("message") or update.get("edited_message")

                        if not message or "text" not in message:
                            continue

                        text = message["text"].strip()
                        chat = message["chat"]
                        chat_id = chat["id"]
                        sender = message.get("from", {})

                        # Filter by chat_id if specified
                        if chat_id_filter and str(chat_id) != str(chat_id_filter):
                            continue

                        command = None
                        args = []
                        if text.startswith("/"):
                            parts = text.split()
                            command = parts[0].split("@")[0].lower()  # Handle /cmd@botname
                            args = parts[1:]

                        # Filter by command if specified
                        if expected_command:
                            norm_expected = expected_command.strip().lower()
                            if not norm_expected.startswith("/"):
                                norm_expected = f"/{norm_expected}"
                            if command != norm_expected:
                                continue

                        payload = {
                            "trigger_type": "telegram",
                            "update_id": update["update_id"],
                            "message_id": message["message_id"],
                            "chat_id": chat_id,
                            "chat_type": chat.get("type"),
                            "username": sender.get("username"),
                            "first_name": sender.get("first_name"),
                            "text": text,
                            "command": command,
                            "args": args
                        }

                        # Dispatch event immediately
                        await on_event(payload)

                except asyncio.CancelledError:
                    break
                except Exception:
                    if self.is_running:
                        await asyncio.sleep(3)

    async def stop(self) -> None:
        self.is_running = False
        if self._task:
            self._task.cancel()
