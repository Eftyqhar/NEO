"""Real-time live terminal dashboard for Neo background daemon."""

import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from neo.core.models import RunResult


class DaemonDashboard:
    """Manages the full-screen live updating TUI for neo start."""

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self.active_listeners: Dict[str, str] = {}
        self.recent_runs: List[Dict[str, Any]] = []
        self.started_at = datetime.now(timezone.utc)

    def set_listener(self, name: str, status: str) -> None:
        self.active_listeners[name] = status

    def add_run(self, result: RunResult) -> None:
        run_dict = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "workflow": result.workflow_name,
            "trigger": result.trigger_type,
            "steps": f"{len(result.steps)}/{len(result.steps)}",
            "duration": f"{result.duration_ms:.1f}ms",
            "status": result.status
        }
        self.recent_runs.insert(0, run_dict)
        if len(self.recent_runs) > 8:
            self.recent_runs.pop()

    def sync_from_ledger(self, ledger) -> None:
        """Pulls latest execution runs from SQLite ledger across all processes."""
        try:
            runs = ledger.get_recent_runs(limit=8)
            new_list = []
            for r in runs:
                try:
                    details = json.loads(r.get("details_json") or "{}")
                    step_count = len(details.get("steps", {}))
                    steps_str = f"{step_count}/{step_count}" if step_count > 0 else "-"
                except Exception:
                    steps_str = "-"

                time_str = r.get("started_at", "").replace("T", " ")[11:19]
                new_list.append({
                    "time": time_str or datetime.now().strftime("%H:%M:%S"),
                    "workflow": r.get("workflow_name", "Unknown"),
                    "trigger": r.get("trigger_type", "manual"),
                    "steps": steps_str,
                    "duration": f"{r.get('duration_ms', 0):.1f}ms",
                    "status": r.get("status", "success")
                })
            self.recent_runs = new_list
        except Exception:
            pass

    def generate_view(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="listeners", size=7),
            Layout(name="runs")
        )

        # Header
        uptime_sec = int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        hdr_text = Text()
        hdr_text.append("=== NEO REAL-TIME AUTOMATION DAEMON ===\n", style="bold cyan")
        hdr_text.append(f"Status: Active | Uptime: {uptime_sec}s | Active Sockets: {len(self.active_listeners)}", style="dim")
        layout["header"].update(Panel(hdr_text, border_style="cyan"))

        # Active Listeners Table
        l_table = Table(show_header=True, header_style="bold magenta", border_style="dim", expand=True)
        l_table.add_column("Workflow", style="bold white", width=35)
        l_table.add_column("Listener / Socket", style="cyan", width=20)
        l_table.add_column("Status", style="green")

        for wf_name, status_str in self.active_listeners.items():
            l_table.add_row(wf_name, status_str, "[ACTIVE] LISTENING")

        layout["listeners"].update(Panel(l_table, title="Active Event Listeners", border_style="blue"))

        # Live Executions Table
        r_table = Table(show_header=True, header_style="bold cyan", border_style="dim", expand=True)
        r_table.add_column("Time", style="dim", width=10)
        r_table.add_column("Workflow", style="bold white", width=35)
        r_table.add_column("Trigger", style="cyan", width=12)
        r_table.add_column("Steps", justify="center", width=8)
        r_table.add_column("Duration", justify="right", width=12)
        r_table.add_column("Status", width=12)

        if not self.recent_runs:
            r_table.add_row("--:--:--", "[dim]No executions yet - listening for events...[/]", "--", "--", "--", "[dim]IDLE[/]")
        else:
            for r in self.recent_runs:
                badge = "[green][OK] SUCCESS[/]" if r["status"] == "success" else "[red][ERR] FAILED[/]"
                r_table.add_row(r["time"], r["workflow"], r["trigger"], r["steps"], r["duration"], badge)

        layout["runs"].update(Panel(r_table, title="Live Execution Log (Sub-second)", border_style="green"))
        return layout
