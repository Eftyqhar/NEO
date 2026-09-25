"""Unit test for OpenAI-compatible endpoint support in AiAction."""

import pytest
from neo.actions.ai_action import AiAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


@pytest.mark.asyncio
async def test_openai_compatible_endpoint_formatting(monkeypatch):
    # Verify that AiAction dispatches to {base_url}/chat/completions
    action = AiAction()
    context = RunContext(trigger={"email_body": "Please refund my transaction #12345"})

    step = StepConfig(
        id="ai_summary",
        type="ai",
        base_url="https://api.hcnsec.cn/v1",
        api_key="test-key-123",
        model="gpt-4o-mini",
        prompt="Extract the transaction number",
        input="{{ steps.trigger.email_body }}"
    )

    recorded_requests = []

    # Mock httpx.AsyncClient.post
    import httpx
    async def mock_post(self, url, json=None, headers=None):
        recorded_requests.append({"url": url, "json": json, "headers": headers})
        class MockResp:
            status_code = 200
            is_success = True
            def json(self):
                return {
                    "choices": [
                        {"message": {"content": "Transaction: #12345"}}
                    ]
                }
        return MockResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await action.execute(step, context)
    assert result["output"] == "Transaction: #12345"
    assert result["model"] == "gpt-4o-mini"
    assert len(recorded_requests) == 1
    assert recorded_requests[0]["url"] == "https://api.hcnsec.cn/v1/chat/completions"
    assert recorded_requests[0]["headers"]["Authorization"] == "Bearer test-key-123"
    assert "Please refund my transaction #12345" in recorded_requests[0]["json"]["messages"][0]["content"]
