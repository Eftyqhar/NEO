"""End-to-End test for real-time Webhook trigger and execution."""

import asyncio
import pytest
import httpx
from neo.core.runner import WorkflowRunner
from neo.core.models import WorkflowConfig, StepConfig, TriggerConfig


@pytest.mark.asyncio
async def test_webhook_e2e():
    runner = WorkflowRunner()
    received_results = []

    wf = WorkflowConfig(
        name="E2E Webhook Test",
        trigger=TriggerConfig(
            type="webhook",
            host="127.0.0.1",
            port=8765,
            path="/webhook/test"
        ),
        steps=[
            StepConfig(
                id="echo_step",
                type="exec",
                command="python -c \"print('Webhook processed for user: {{ steps.trigger.data.user }}')\""
            )
        ]
    )

    # Setup listener
    trigger = runner.create_trigger(wf)
    runner.on_run_complete = lambda res: received_results.append(res)

    async def on_event(payload):
        await runner.execute_workflow(wf, payload)

    await trigger.start(on_event)

    try:
        # Give server 100ms to bind socket
        await asyncio.sleep(0.1)

        # Send HTTP POST to webhook endpoint
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://127.0.0.1:8765/webhook/test",
                json={"user": "Alice", "action": "login"}
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "dispatched"

        # Wait for async execution on Windows process spawn
        for _ in range(40):
            if len(received_results) > 0:
                break
            await asyncio.sleep(0.1)

        assert len(received_results) == 1
        run = received_results[0]
        assert run.status == "success"
        assert "echo_step" in run.steps
        assert "Webhook processed for user: Alice" in run.steps["echo_step"].data["stdout"]

    finally:
        await trigger.stop()
