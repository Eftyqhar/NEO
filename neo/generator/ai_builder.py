"""Natural language to YAML workflow generator with OpenAI-compatible & Gemini support."""

import os
import re
from typing import Optional
from dotenv import load_dotenv
import httpx
import yaml

load_dotenv()

SYSTEM_PROMPT = """
You are the workflow generator for Neo, a lightweight CLI workflow automation engine like n8n.
Convert the user's natural language automation request into a clean, valid YAML workflow.

Neo YAML Workflow Specification:
name: "Workflow Name"
description: "Description"
trigger:
  type: imap | telegram | webhook | cron | file_watch | manual
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


def generate_workflow_yaml(prompt: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> str:
    """Generates a validated YAML workflow from natural language using OpenAI-compatible API or Gemini."""
    
    # 1. Try OpenAI-compatible API (e.g. https://api.hcnsec.cn/v1)
    openai_base = base_url or os.environ.get("OPENAI_BASE_URL") or os.environ.get("AI_BASE_URL")
    openai_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY")
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if openai_base or openai_key:
        norm_base = (openai_base or "https://api.openai.com/v1").rstrip("/")
        if not norm_base.endswith("/v1") and not norm_base.endswith("/chat/completions"):
            endpoint = f"{norm_base}/v1/chat/completions"
        elif norm_base.endswith("/v1"):
            endpoint = f"{norm_base}/chat/completions"
        else:
            endpoint = norm_base

        headers = {"Content-Type": "application/json"}
        if openai_key:
            headers["Authorization"] = f"Bearer {openai_key}"

        payload = {
            "model": openai_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Create workflow: {prompt}"}
            ],
            "temperature": 0.2
        }

        with httpx.Client(timeout=45.0) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            data = resp.json()
            if not resp.is_success or "choices" not in data or len(data["choices"]) == 0:
                err_msg = data.get("error", {}).get("message") if isinstance(data, dict) else resp.text
                raise RuntimeError(f"OpenAI-compatible generation error ({resp.status_code}): {err_msg}")

            raw_yaml = data["choices"][0]["message"]["content"].strip()
            raw_yaml = re.sub(r"^```yaml\s*", "", raw_yaml)
            raw_yaml = re.sub(r"^```\s*", "", raw_yaml)
            raw_yaml = re.sub(r"\s*```$", "", raw_yaml).strip()

            yaml.safe_load(raw_yaml)
            return raw_yaml

    # 2. Try Gemini API
    gemini_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser Request: {prompt}"}]}]
        }

        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=payload)
            data = resp.json()
            if not resp.is_success or "candidates" not in data:
                raise RuntimeError(f"Gemini API generation error: {data}")

            raw_yaml = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            raw_yaml = re.sub(r"^```yaml\s*", "", raw_yaml)
            raw_yaml = re.sub(r"^```\s*", "", raw_yaml)
            raw_yaml = re.sub(r"\s*```$", "", raw_yaml).strip()

            yaml.safe_load(raw_yaml)
            return raw_yaml

    raise ValueError(
        "AI workflow generation requires OPENAI_BASE_URL (e.g. https://api.hcnsec.cn/v1), OPENAI_API_KEY, or GEMINI_API_KEY in your .env file."
    )
