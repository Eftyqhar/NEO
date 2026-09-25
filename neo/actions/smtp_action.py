"""Asynchronous SMTP email action node using aiosmtplib."""

from email.message import EmailMessage
import os
from typing import Any, Dict, List, Union
import aiosmtplib

from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


class SmtpAction(BaseAction):
    """Sends transactional and templated emails via SMTP."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        host = resolved.get("host") or resolved.get("smtp_host")
        port = int(resolved.get("port", 587))
        username = resolved.get("username") or resolved.get("user")
        password = resolved.get("password") or resolved.get("pass")
        
        if not host:
            raise ValueError(f"Step '{step.id}' (smtp) missing required 'host' configuration.")

        from_addr = resolved.get("from") or resolved.get("from_email") or username
        to_addr = resolved.get("to")
        if not to_addr:
            raise ValueError(f"Step '{step.id}' (smtp) missing required 'to' recipient.")

        recipients: List[str] = [to_addr] if isinstance(to_addr, str) else list(to_addr)
        subject = resolved.get("subject", "Notification from Neo")
        body = resolved.get("body", "")
        html = resolved.get("html")
        attachments = resolved.get("attachments", [])

        # Build standard MIME email
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        if body:
            msg.set_content(body)
        if html:
            if not body:
                msg.set_content("Please enable HTML to view this message.")
            msg.add_alternative(html, subtype="html")

        # Handle file attachments
        if isinstance(attachments, str):
            attachments = [attachments]
        for file_path in attachments:
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    file_data = f.read()
                    file_name = os.path.basename(file_path)
                    msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=file_name)

        # Connection encryption parameters
        use_tls = resolved.get("use_tls", port == 465)
        start_tls = resolved.get("start_tls", port == 587)

        client = aiosmtplib.SMTP(
            hostname=host,
            port=port,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=30.0
        )

        async with client:
            if username and password:
                await client.login(username, password)
            response = await client.send_message(msg)

        return {
            "ok": True,
            "recipients": recipients,
            "response": str(response)
        }
