"""Template resolution and condition evaluation using Jinja2."""

import json
from typing import Any, Dict, List, Union
import jinja2
from jinja2 import Environment, BaseLoader, select_autoescape

from neo.core.context import RunContext


class TemplateEngine:
    """Evaluates expressions and resolves templates against RunContext."""

    def __init__(self):
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(['html', 'xml'], default=False),
            trim_blocks=True,
            lstrip_blocks=True
        )
        # Add useful filters
        self.env.filters["to_json"] = lambda v, indent=None: json.dumps(v, indent=indent, default=str)
        self.env.filters["from_json"] = lambda v: json.loads(v) if isinstance(v, str) else v

    def render_string(self, template_str: str, context: RunContext) -> str:
        """Renders a Jinja2 template string using context data."""
        if "{{" not in template_str and "{%" not in template_str:
            return template_str
        try:
            template = self.env.from_string(template_str)
            return template.render(**context.get_template_scope())
        except Exception as e:
            raise ValueError(f"Failed to render template '{template_str}': {e}") from e

    def resolve(self, value: Any, context: RunContext) -> Any:
        """Recursively resolves Jinja2 expressions inside strings, dicts, and lists."""
        if isinstance(value, str):
            return self.render_string(value, context)
        elif isinstance(value, dict):
            return {k: self.resolve(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve(item, context) for item in value]
        return value

    def evaluate_condition(self, condition_expr: str, context: RunContext) -> bool:
        """Evaluates a Jinja2 boolean expression (e.g. 'steps.trigger.unread == True')."""
        if not condition_expr or not condition_expr.strip():
            return True
        wrapped_expr = f"{{% if {condition_expr.strip()} %}}true{{% else %}}false{{% endif %}}"
        try:
            rendered = self.render_string(wrapped_expr, context).strip().lower()
            return rendered == "true"
        except Exception as e:
            raise ValueError(f"Failed to evaluate condition '{condition_expr}': {e}") from e
