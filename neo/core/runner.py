"""Workflow loading, trigger orchestration, and lifecycle management."""

import asyncio
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional
import yaml
from dotenv import load_dotenv

from neo.core.models import RunResult, WorkflowConfig
from neo.core.engine import WorkflowEngine
from neo.core.ledger import ExecutionLedger
from neo.triggers.base import BaseTrigger
from neo.triggers.imap_idle import ImapIdleTrigger
from neo.triggers.telegram_trigger import TelegramTrigger
from neo.triggers.webhook import WebhookTrigger
from neo.triggers.cron import CronTrigger
from neo.triggers.file_watch import FileWatchTrigger


class WorkflowRunner:
    """Manages workflows, active background triggers, and execution lifecycle."""

    def __init__(self, ledger: Optional[ExecutionLedger] = None):
        load_dotenv()  # Load .env variables into os.environ
        self.engine = WorkflowEngine()
        self.ledger = ledger or ExecutionLedger()
        self.workflows: Dict[str, WorkflowConfig] = {}
        self.active_triggers: Dict[str, BaseTrigger] = {}
        self.on_run_complete: Optional[Callable[[RunResult], None]] = None

    def load_workflow_file(self, file_path: str) -> WorkflowConfig:
        """Parses a YAML workflow file into a validated WorkflowConfig."""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
        workflow = WorkflowConfig.model_validate(raw_data)
        self.workflows[file_path] = workflow
        return workflow

    def load_workflows_from_dir(self, dir_path: str = "./workflows") -> List[WorkflowConfig]:
        """Loads all .yaml and .yml files from a workflows directory."""
        loaded = []
        path = Path(dir_path)
        if not path.exists():
            return loaded

        for file in path.glob("*.y*ml"):
            try:
                wf = self.load_workflow_file(str(file))
                loaded.append(wf)
            except Exception as e:
                print(f"[!] Warning: Failed to load workflow '{file}': {e}")
        return loaded

    def create_trigger(self, workflow: WorkflowConfig) -> BaseTrigger:
        """Instantiates the appropriate real-time trigger for a workflow."""
        ttype = workflow.trigger.type.lower()
        if ttype in ("imap", "imap_idle"):
            return ImapIdleTrigger(workflow.trigger, self.engine.templater)
        elif ttype in ("telegram", "tg"):
            return TelegramTrigger(workflow.trigger, self.engine.templater)
        elif ttype in ("webhook", "http_in"):
            return WebhookTrigger(workflow.trigger, self.engine.templater)
        elif ttype in ("cron", "schedule", "interval"):
            return CronTrigger(workflow.trigger, self.engine.templater)
        elif ttype in ("file_watch", "file"):
            return FileWatchTrigger(workflow.trigger, self.engine.templater)
        else:
            raise ValueError(f"Unsupported trigger type: '{ttype}'")

    async def execute_workflow(self, workflow: WorkflowConfig, trigger_data: dict) -> RunResult:
        """Executes a workflow pipeline and logs the result."""
        result = await self.engine.execute(workflow, trigger_data)
        self.ledger.record_run(result)

        if self.on_run_complete:
            self.on_run_complete(result)

        return result

    async def start_daemon(self, dir_path: str = "./workflows") -> None:
        """Starts real-time listener daemons for all enabled workflows in directory."""
        workflows = self.load_workflows_from_dir(dir_path)

        for wf in workflows:
            if not wf.enabled:
                continue

            try:
                trigger = self.create_trigger(wf)
                self.active_triggers[wf.name] = trigger

                # Event dispatcher closure
                async def dispatch_event(payload: dict, target_wf=wf):
                    await self.execute_workflow(target_wf, payload)

                await trigger.start(dispatch_event)
            except Exception as e:
                print(f"[!] Error starting trigger for workflow '{wf.name}': {e}")

    async def stop_daemon(self) -> None:
        """Gracefully stops all active triggers."""
        for name, trigger in self.active_triggers.items():
            try:
                await trigger.stop()
            except Exception:
                pass
        self.active_triggers.clear()
