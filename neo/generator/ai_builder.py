"""Natural language to YAML workflow generator."""

import os
import re
from typing import Optional
import httpx
import yaml

SYSTEM_PROMPT = """
You are the workflow generator for Neo, a lightweight CLI workflow automation engine like n8n.
Convert the user's natural language automation request into a clean, valid YAML workflow.

Neo YAML Workflow Specification:
name: "Workflow Name"
description: "Description"
trigger:
  type: imap | telegram | webhook | cron | file_watch
  # Trigger-specific parameters:
  # imap: host, port (993), username ("{{ env.EMAIL_USER }}"), password ("{{ env.EMAIL_PASS }}"), folder ("INBOX")
  # telegram: bot_token ("{{ env.TELEGRAM_BOT_TOKEN }}"), command (e.g. "/status")
  # webhook: port (8080), path ("/webhook/demo"), secret (optional)
  # cron: schedule (e.g. "0 9 * * *") or interval_seconds
  # file_watch: path ("./downloads"), patterns (["*.pdf", "*.csv"])
steps:
  - id: step_id
    type: http | exec | smtp | telegram | filter | ai
    # Action parameters:
    # http: method (GET|POST), url, headers, json
    # exec: command (e.g. "python script.py")
    # smtp: host, port (587), username, password, to, subject, body, html
    # telegram: bot_token, chat_id, message (markdown format)
    # filter: condition (Jinja2 boolean expression, e.g. "'urgent' in steps.trigger.subject.lower()")
    # ai: prompt, input ("{{ steps.trigger.body }}")

Output ONLY raw YAML without explanation.
"""


def generate_workflow_yaml(prompt: str, api_key: Optional[str] = None) -> str:
    """Calls Gemini API to generate a validated YAML workflow from natural language."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("AI workflow generation requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser Request: {prompt}"}]}]
    }

    with httpx.Client(timeout=45.0) as client:
        resp = client.post(url, json=payload)
        data = resp.json()
        if not resp.is_success or "candidates" not in data:
            raise RuntimeError(f"Gemini API generation error: {data}")

        raw_yaml = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Clean markdown code blocks if present
        raw_yaml = re.sub(r"^```yaml\s*", "", raw_yaml)
        raw_yaml = re.sub(r"^```\s*", "", raw_yaml)
        raw_yaml = re.sub(r"\s*```$", "", raw_yaml).strip()

        # Validate that it is valid YAML
        yaml.safe_load(raw_yaml)
        return raw_yaml
