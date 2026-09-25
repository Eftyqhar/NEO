"""Pydantic schemas and data models for Neo workflows and executions."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class TriggerConfig(BaseModel):
    """Configuration for a workflow trigger."""
    model_config = ConfigDict(extra="allow")

    type: str = Field(description="Trigger type: e.g. 'imap', 'telegram', 'webhook', 'cron', 'file_watch', 'manual'")
    # Additional trigger-specific fields like host, port, bot_token, schedule, etc. will be dynamically captured.


class StepConfig(BaseModel):
    """Configuration for a single step in a workflow pipeline."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Unique identifier for the step (referenced as steps.<id>)")
    type: str = Field(description="Action/node type: 'smtp', 'telegram', 'http', 'exec', 'filter', 'ai', 'file'")
    condition: Optional[str] = Field(default=None, description="Optional Jinja2 condition expression to execute this step")
    continue_on_error: bool = Field(default=False, description="Whether to continue pipeline execution if this step fails")


class WorkflowConfig(BaseModel):
    """Full workflow specification parsed from YAML."""
    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Human-readable name of the workflow")
    description: Optional[str] = Field(default=None, description="Brief description of workflow purpose")
    enabled: bool = Field(default=True, description="Whether the workflow is active")
    trigger: TriggerConfig = Field(description="The event trigger specification")
    steps: List[StepConfig] = Field(default_factory=list, description="Ordered execution steps")


class StepResult(BaseModel):
    """Result of an individual step execution."""
    step_id: str
    status: str = Field(description="'success', 'skipped', or 'failed'")
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class RunResult(BaseModel):
    """Full execution summary of a workflow run."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_name: str
    status: str = Field(default="pending", description="'success', 'failed', or 'running'")
    trigger_type: str
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    steps: Dict[str, StepResult] = Field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
