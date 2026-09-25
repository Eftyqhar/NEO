"""Telegram Bot action node for sending messages and notifications."""

from typing import Any, Dict
import httpx

from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


class TelegramAction(BaseAction):
    """Sends messages, alerts, and documents to Telegram chats via Bot API."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        bot_token = resolved.get("bot_token") or resolved.get("token")
        chat_id = resolved.get("chat_id")
        message = resolved.get("message") or resolved.get("text")
        parse_mode = resolved.get("parse_mode", "Markdown")

        if not bot_token:
            raise ValueError(f"Step '{step.id}' (telegram) missing required 'bot_token'.")
        if not chat_id:
            raise ValueError(f"Step '{step.id}' (telegram) missing required 'chat_id'.")
        if not message:
            raise ValueError(f"Step '{step.id}' (telegram) missing required 'message' or 'text'.")

        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": resolved.get("disable_web_page_preview", False)
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(api_url, json=payload)
            data = resp.json()

            if not data.get("ok"):
                error_desc = data.get("description", "Unknown Telegram API error")
                if not step.continue_on_error:
                    raise RuntimeError(f"Telegram API error: {error_desc}")

            return {
                "ok": data.get("ok", False),
                "message_id": data.get("result", {}).get("message_id"),
                "result": data.get("result", {})
            }
