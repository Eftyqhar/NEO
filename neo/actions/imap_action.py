"""IMAP action node for on-demand email fetching."""

import email
from email.header import decode_header
import os
from typing import Any, Dict, Optional
import aioimaplib

from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


def _decode_mime_str(s: Optional[str]) -> str:
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


class ImapAction(BaseAction):
    """Fetches real emails on demand from an IMAP inbox."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        host = resolved.get("host") or os.environ.get("EMAIL_HOST") or "imap.gmail.com"
        port = int(resolved.get("port", 993))
        username = resolved.get("username") or os.environ.get("EMAIL_USER")
        password = resolved.get("password") or os.environ.get("EMAIL_PASS")
        folder = resolved.get("folder", "INBOX")
        criteria = resolved.get("criteria", "ALL")

        if not username or not password:
            raise ValueError(f"Step '{step.id}' (imap) requires 'username' and 'password'.")

        client = aioimaplib.IMAP4_SSL(host=host, port=port)
        try:
            await client.wait_hello_from_server()
            await client.login(username, password)
            await client.select(folder)

            res, data = await client.search(criteria)
            if res != "OK" or not data or not data[0]:
                return {"found": False, "message": "No emails found matching criteria."}

            msg_ids = data[0].split()
            latest_id = msg_ids[-1].decode()

            fetch_res, fetch_data = await client.fetch(latest_id, "(RFC822)")
            if fetch_res != "OK":
                raise RuntimeError(f"Failed to fetch email ID {latest_id}")

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

            snippet = body[:300].replace("\n", " ").strip() if body else ""

            return {
                "found": True,
                "msg_id": latest_id,
                "from": sender,
                "to": to,
                "subject": subject,
                "date": date_str,
                "body": body,
                "snippet": snippet
            }
        finally:
            try:
                await client.logout()
            except Exception:
                pass
