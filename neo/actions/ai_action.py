"""AI LLM Transformation and text processing action node."""

import json
import os
from typing import Any, Dict, Optional
import httpx

from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


class AiAction(BaseAction):
    """Transforms, summarizes, or extracts structured JSON from text using LLMs."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        prompt = resolved.get("prompt")
        input_text = resolved.get("input") or resolved.get("text", "")
        model = resolved.get("model", "gemini-2.5-flash")
        api_key = resolved.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if not prompt:
            raise ValueError(f"Step '{step.id}' (ai) missing required 'prompt'.")

        full_prompt = f"{prompt}\n\nInput Context:\n{input_text}" if input_text else prompt

        # If Gemini API key is available
        if api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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

        # Check for local Ollama fallback if available
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

        raise ValueError("AI action requires GEMINI_API_KEY, GOOGLE_API_KEY, or a running local Ollama instance.")
