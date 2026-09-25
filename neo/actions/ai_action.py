"""AI LLM Transformation and text processing action node with OpenAI-compatible & Gemini support."""

import json
import os
from typing import Any, Dict, Optional
import httpx

from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


class AiAction(BaseAction):
    """Transforms, summarizes, or extracts structured JSON from text using OpenAI-compatible APIs or Gemini."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        prompt = resolved.get("prompt")
        input_text = resolved.get("input") or resolved.get("text", "")
        if not prompt:
            raise ValueError(f"Step '{step.id}' (ai) missing required 'prompt'.")

        full_prompt = f"{prompt}\n\nInput Context:\n{input_text}" if input_text else prompt

        # 1. Check for OpenAI-compatible API (e.g. https://api.hcnsec.cn or custom endpoint)
        base_url = (
            resolved.get("base_url") 
            or resolved.get("api_base") 
            or os.environ.get("OPENAI_BASE_URL") 
            or os.environ.get("AI_BASE_URL")
        )
        openai_key = (
            resolved.get("api_key") 
            or os.environ.get("OPENAI_API_KEY") 
            or os.environ.get("AI_API_KEY")
        )
        openai_model = (
            resolved.get("model") 
            or os.environ.get("OPENAI_MODEL") 
            or "gpt-4o-mini"
        )

        # If base_url or OpenAI key is set, use OpenAI-compatible /chat/completions
        if base_url or openai_key:
            norm_base = (base_url or "https://api.openai.com/v1").rstrip("/")
            if not norm_base.endswith("/v1") and not norm_base.endswith("/chat/completions"):
                endpoint = f"{norm_base}/v1/chat/completions"
            elif norm_base.endswith("/v1"):
                endpoint = f"{norm_base}/chat/completions"
            else:
                endpoint = norm_base

            headers = {
                "Content-Type": "application/json"
            }
            if openai_key:
                headers["Authorization"] = f"Bearer {openai_key}"

            payload = {
                "model": openai_model,
                "messages": [
                    {"role": "user", "content": full_prompt}
                ],
                "temperature": float(resolved.get("temperature", 0.7))
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                data = resp.json()
                if resp.is_success and "choices" in data and len(data["choices"]) > 0:
                    text_out = data["choices"][0]["message"]["content"].strip()
                    return {"output": text_out, "model": openai_model, "endpoint": endpoint}
                else:
                    err_msg = data.get("error", {}).get("message") if isinstance(data, dict) else resp.text
                    raise RuntimeError(f"OpenAI-compatible API error ({resp.status_code}): {err_msg}")

        # 2. Check for Google Gemini API
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if gemini_key:
            model = resolved.get("model", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}]
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if resp.is_success and "candidates" in data:
                    text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return {"output": text_out, "model": model}
                else:
                    raise RuntimeError(f"Gemini API error: {data.get('error', {}).get('message', resp.text)}")

        # 3. Check for local Ollama fallback
        ollama_url = resolved.get("ollama_url") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": resolved.get("ollama_model", "llama3"), "prompt": full_prompt, "stream": False}
                )
                if resp.is_success:
                    return {"output": resp.json().get("response", "").strip(), "model": "ollama"}
        except Exception:
            pass

        raise ValueError(
            "AI action requires OPENAI_BASE_URL (e.g. https://api.hcnsec.cn/v1), OPENAI_API_KEY, or GEMINI_API_KEY in your .env file."
        )
