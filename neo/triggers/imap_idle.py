"""Real-Time IMAP IDLE (RFC 2177) push listener using aioimaplib."""

import asyncio
import email
from email.header import decode_header
import os
import re
from typing import Any, Awaitable, Callable, Dict, Optional
import aioimaplib

from neo.triggers.base import BaseTrigger
from neo.core.models import TriggerConfig
from neo.core.context import RunContext


def _decode_mime_str(s: Optional[str]) -> str:
    """Decodes MIME encoded headers (e.g., =?utf-8?B?...?=)."""
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    result = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result)


class ImapIdleTrigger(BaseTrigger):
    """Listens for incoming emails in real-time via IMAP IDLE push socket."""

    def __init__(self, config: TriggerConfig, templater=None):
        super().__init__(config, templater)
        self.client: Optional[aioimaplib.IMAP4_SSL] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self, on_event: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self.is_running = True
        context = RunContext()
        cfg = self.templater.resolve(self.config.model_dump(), context)

        raw_host = cfg.get("host")
        host = (raw_host.strip() if isinstance(raw_host, str) else "") or "imap.gmail.com"
        port = int(cfg.get("port", 993))
        username = cfg.get("username") or cfg.get("user") or ""
        password = cfg.get("password") or cfg.get("pass") or ""
        folder = cfg.get("folder", "INBOX")

        if not username or not password or "your_" in username or "your_" in password:
            print("[!] IMAP trigger skipped: EMAIL_USER / EMAIL_PASS contains placeholders or is not set.")
            self.is_running = False
            return

        self._task = asyncio.create_task(self._listen_loop(host, port, username, password, folder, on_event))

    async def _listen_loop(
        self, host: str, port: int, user: str, pwd: str, folder: str,
        on_event: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        while self.is_running:
            try:
                self.client = aioimaplib.IMAP4_SSL(host=host, port=port)
                await self.client.wait_hello_from_server()
                await self.client.login(user, pwd)
                await self.client.select(folder)

                # Track highest seen UID or search UNSEEN
                res, data = await self.client.search("UNSEEN")
                unseen_ids = data[0].split() if res == "OK" and data and data[0] else []
                last_seen_count = len(unseen_ids)

                while self.is_running:
                    # Enter IMAP IDLE state (RFC 2177 push)
                    idle = await self.client.idle_start()

                    try:
                        # Wait for server push notification (keep-alive refresh every 15 min)
                        push_line = await asyncio.wait_for(self.client.wait_server_push(), timeout=900)
                    except asyncio.TimeoutError:
                        self.client.idle_done()
                        await self.client.noop()
                        continue

                    self.client.idle_done()

                    # Check for new messages
                    res, data = await self.client.search("UNSEEN")
                    if res == "OK" and data and data[0]:
                        current_unseen = data[0].split()
                        for msg_num in current_unseen:
                            fetch_res, fetch_data = await self.client.fetch(msg_num.decode(), "(RFC822)")
                            if fetch_res == "OK":
                                raw_email = fetch_data[1]
                                msg = email.message_from_bytes(raw_email)

                                subject = _decode_mime_str(msg.get("Subject"))
                                sender = _decode_mime_str(msg.get("From"))
                                to = _decode_mime_str(msg.get("To"))
                                date_str = msg.get("Date", "")

                                body = ""
                                html = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        ctype = part.get_content_type()
                                        if ctype == "text/plain" and not body:
                                            body = part.get_payload(decode=True).decode(errors="replace")
                                        elif ctype == "text/html" and not html:
                                            html = part.get_payload(decode=True).decode(errors="replace")
                                else:
                                    body = msg.get_payload(decode=True).decode(errors="replace")

                                snippet = body[:250].replace("\n", " ") if body else ""

                                payload = {
                                    "trigger_type": "imap",
                                    "from": sender,
                                    "to": to,
                                    "subject": subject,
                                    "date": date_str,
                                    "body": body,
                                    "html": html,
                                    "snippet": snippet,
                                    "raw_msg_id": msg.get("Message-ID", "")
                                }

                                # Dispatch immediately to workflow
                                await on_event(payload)

            except Exception as e:
                if self.is_running:
                    # Reconnect after backoff
                    await asyncio.sleep(5)
            finally:
                if self.client:
                    try:
                        await self.client.logout()
                    except Exception:
                        pass

    async def stop(self) -> None:
        self.is_running = False
        if self.client:
            try:
                self.client.idle_done()
            except Exception:
                pass
        if self._task:
            self._task.cancel()
