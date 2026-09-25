"""Unit tests for Jinja2 template engine and condition evaluation."""

import pytest
from neo.core.context import RunContext
from neo.core.templating import TemplateEngine


def test_render_string():
    templater = TemplateEngine()
    context = RunContext(
        trigger={"sender": "alice@test.com", "subject": "Urgent Alert"},
        steps={"check_step": {"status_code": 200}}
    )

    rendered = templater.render_string("Email from {{ trigger.sender }} (Code: {{ steps.check_step.status_code }})", context)
    assert rendered == "Email from alice@test.com (Code: 200)"


def test_evaluate_condition():
    templater = TemplateEngine()
    context = RunContext(
        trigger={"amount": 150, "keyword": "urgent"}
    )

    assert templater.evaluate_condition("trigger.amount > 100", context) is True
    assert templater.evaluate_condition("trigger.amount < 50", context) is False
    assert templater.evaluate_condition("'urgent' in trigger.keyword", context) is True


def test_recursive_resolve():
    templater = TemplateEngine()
    context = RunContext(trigger={"name": "Neo"})

    data = {
        "title": "Welcome {{ trigger.name }}",
        "nested": {"greeting": "Hello {{ trigger.name }}"},
        "items": ["Item for {{ trigger.name }}", 123]
    }

    resolved = templater.resolve(data, context)
    assert resolved["title"] == "Welcome Neo"
    assert resolved["nested"]["greeting"] == "Hello Neo"
    assert resolved["items"][0] == "Item for Neo"
    assert resolved["items"][1] == 123
