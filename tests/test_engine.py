"""Unit tests for the DAG workflow execution engine."""

import pytest
import asyncio
from neo.core.engine import WorkflowEngine
from neo.core.models import WorkflowConfig, StepConfig, TriggerConfig


@pytest.mark.asyncio
async def test_workflow_execution_success():
    engine = WorkflowEngine()

    workflow = WorkflowConfig(
        name="Test Workflow",
        trigger=TriggerConfig(type="manual"),
        steps=[
            StepConfig(
                id="step1",
                type="exec",
                command="python -c \"print('hello from step 1')\""
            ),
            StepConfig(
                id="step2",
                type="exec",
                command="python -c \"print('received: {{ steps.step1.stdout }}')\""
            )
        ]
    )

    result = await engine.execute(workflow, {"manual_trigger": True})

    assert result.status == "success"
    assert "step1" in result.steps
    assert "step2" in result.steps
    assert result.steps["step1"].data["stdout"] == "hello from step 1"
    assert "received: hello from step 1" in result.steps["step2"].data["stdout"]


@pytest.mark.asyncio
async def test_workflow_filter_stop():
    engine = WorkflowEngine()

    workflow = WorkflowConfig(
        name="Filter Test Workflow",
        trigger=TriggerConfig(type="manual"),
        steps=[
            StepConfig(
                id="filter_step",
                type="filter",
                condition="steps.trigger.level == 'high'"
            ),
            StepConfig(
                id="should_not_run",
                type="exec",
                command="python -c \"print('should not see this')\""
            )
        ]
    )

    # Condition fails (level is 'low')
    result = await engine.execute(workflow, {"level": "low"})

    assert result.status == "success"
    assert result.steps["filter_step"].status == "filtered"
    assert "should_not_run" not in result.steps
