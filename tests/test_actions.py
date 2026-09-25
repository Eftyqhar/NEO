"""Unit tests for Action nodes."""

import pytest
import asyncio
from neo.actions.exec_action import ExecAction
from neo.actions.http_action import HttpAction
from neo.core.models import StepConfig
from neo.core.context import RunContext


@pytest.mark.asyncio
async def test_exec_action():
    action = ExecAction()
    context = RunContext(trigger={"msg": "Neo test"})

    step = StepConfig(
        id="test_exec",
        type="exec",
        command="python -c \"print('{{ trigger.msg }}')\""
    )

    result = await action.execute(step, context)
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert result["stdout"] == "Neo test"


@pytest.mark.asyncio
async def test_http_action():
    action = HttpAction()
    context = RunContext(trigger={})

    step = StepConfig(
        id="test_http",
        type="http",
        method="GET",
        url="https://httpbin.org/get",
        params={"query": "neo"}
    )

    result = await action.execute(step, context)
    assert result["status_code"] == 200
    assert result["ok"] is True
    assert isinstance(result["data"], dict)
    assert result["data"]["args"]["query"] == "neo"
