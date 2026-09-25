"""Asynchronous HTTP Webhook server trigger using aiohttp."""

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional
from aiohttp import web

from neo.triggers.base import BaseTrigger
from neo.core.models import TriggerConfig
from neo.core.context import RunContext


class WebhookTrigger(BaseTrigger):
    """Listens for incoming HTTP POST webhooks in real time."""

    def __init__(self, config: TriggerConfig, templater=None):
        super().__init__(config, templater)
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

    async def start(self, on_event: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self.is_running = True
        context = RunContext()
        cfg = self.templater.resolve(self.config.model_dump(), context)

        host = cfg.get("host", "0.0.0.0")
        port = int(cfg.get("port", 8080))
        path = cfg.get("path", "/webhook")
        if not path.startswith("/"):
            path = f"/{path}"
        secret = cfg.get("secret")

        app = web.Application()

        async def handle_post(request: web.Request) -> web.Response:
            if secret:
                header_secret = request.headers.get("X-Webhook-Secret") or request.headers.get("Authorization")
                if header_secret != secret and header_secret != f"Bearer {secret}":
                    return web.json_response({"error": "Unauthorized"}, status=401)

            try:
                body = await request.json()
            except Exception:
                body = await request.text()

            payload = {
                "trigger_type": "webhook",
                "path": request.path,
                "method": request.method,
                "headers": dict(request.headers),
                "query": dict(request.query),
                "body": body,
                "data": body if isinstance(body, dict) else {"raw": body}
            }

            # Asynchronously dispatch event without blocking response
            asyncio.create_task(on_event(payload))
            return web.json_response({"ok": True, "status": "dispatched"})

        async def handle_get(request: web.Request) -> web.Response:
            return web.json_response({"status": "ready", "path": path})

        app.router.add_post(path, handle_post)
        app.router.add_get(path, handle_get)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, host, port)
        await self.site.start()

    async def stop(self) -> None:
        self.is_running = False
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
