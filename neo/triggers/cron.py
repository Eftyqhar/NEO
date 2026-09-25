"""Time-based scheduling trigger using APScheduler."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger as ApCronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from neo.triggers.base import BaseTrigger
from neo.core.models import TriggerConfig
from neo.core.context import RunContext


class CronTrigger(BaseTrigger):
    """Fires workflows on cron schedules or fixed intervals."""

    def __init__(self, config: TriggerConfig, templater=None):
        super().__init__(config, templater)
        self.scheduler: Optional[AsyncIOScheduler] = None

    async def start(self, on_event: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self.is_running = True
        context = RunContext()
        cfg = self.templater.resolve(self.config.model_dump(), context)

        self.scheduler = AsyncIOScheduler()

        schedule_expr = cfg.get("schedule") or cfg.get("cron")
        interval_secs = cfg.get("interval_seconds") or cfg.get("interval_sec")
        interval_mins = cfg.get("interval_minutes") or cfg.get("interval_min")

        async def job():
            payload = {
                "trigger_type": "cron",
                "fired_at": datetime.now(timezone.utc).isoformat(),
                "schedule": schedule_expr or f"interval_{interval_secs or interval_mins}"
            }
            await on_event(payload)

        if schedule_expr:
            # 5-field cron: minute hour day-of-month month day-of-week
            parts = schedule_expr.split()
            if len(parts) == 5:
                trigger = ApCronTrigger(
                    minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]
                )
            else:
                trigger = ApCronTrigger.from_crontab(schedule_expr)
            self.scheduler.add_job(job, trigger)
        elif interval_secs:
            self.scheduler.add_job(job, IntervalTrigger(seconds=int(interval_secs)))
        elif interval_mins:
            self.scheduler.add_job(job, IntervalTrigger(minutes=int(interval_mins)))
        else:
            raise ValueError("Cron trigger requires 'schedule' (cron format) or 'interval_seconds'.")

        self.scheduler.start()

    async def stop(self) -> None:
        self.is_running = False
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
