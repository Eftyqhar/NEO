"""HTTP / REST action node."""

from typing import Any, Dict
import httpx

from neo.actions.base import BaseAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


class HttpAction(BaseAction):
    """Executes asynchronous HTTP requests."""

    async def execute(self, step: StepConfig, context: RunContext) -> Dict[str, Any]:
        # Step fields are dynamically resolved
        step_dict = step.model_dump()
        resolved = self.templater.resolve(step_dict, context)

        method = str(resolved.get("method", resolved.get("action", "GET"))).upper()
        url = resolved.get("url")
        if not url:
            raise ValueError(f"Step '{step.id}' (http) missing required 'url' parameter.")

        headers = resolved.get("headers", {})
        params = resolved.get("params")
        json_data = resolved.get("json", resolved.get("body"))
        data = resolved.get("data")
        timeout = float(resolved.get("timeout", 30.0))

        # Handle basic/bearer auth shortcuts
        if "auth_bearer" in resolved:
            headers["Authorization"] = f"Bearer {resolved['auth_bearer']}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            req_kwargs = {"headers": headers, "params": params}
            if json_data is not None and isinstance(json_data, (dict, list)):
                req_kwargs["json"] = json_data
            elif json_data is not None:
                req_kwargs["content"] = str(json_data)
            elif data is not None:
                req_kwargs["data"] = data

            resp = await client.request(method, url, **req_kwargs)

            try:
                parsed_json = resp.json()
            except Exception:
                parsed_json = None

            return {
                "status_code": resp.status_code,
                "ok": resp.is_success,
                "headers": dict(resp.headers),
                "data": parsed_json if parsed_json is not None else resp.text,
                "text": resp.text
            }
