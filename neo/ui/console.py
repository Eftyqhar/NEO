"""Rich console printing, tables, and badge formatters."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import List, Dict, Any
from neo.core.models import RunResult

console = Console()


def print_banner():
    """Prints the Neo engine startup banner."""
    banner_text = Text()
    banner_text.append("=== NEO AUTOMATION ENGINE ===\n", style="bold cyan")
    banner_text.append("Lightweight | Real-Time | Terminal-First Workflow Orchestrator", style="dim")
    panel = Panel(banner_text, border_style="cyan", padding=(0, 2))
    console.print(panel)


def print_run_result(result: RunResult):
    """Renders a formatted summary table for a workflow execution run."""
    status_style = "bold green" if result.status == "success" else "bold red"
    status_icon = "[OK]" if result.status == "success" else "[ERR]"

    title = f"Workflow: [bold white]{result.workflow_name}[/] | Status: [{status_style}]{status_icon} {result.status.upper()}[/] | Time: [cyan]{result.duration_ms:.1f}ms[/]"
    
    table = Table(title=title, show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Step ID", style="bold cyan", width=20)
    table.add_column("Status", width=12)
    table.add_column("Duration", justify="right", width=12)
    table.add_column("Output / Details", style="dim")

    for step_id, step_res in result.steps.items():
        if step_res.status == "success":
            badge = "[green][OK] SUCCESS[/]"
        elif step_res.status == "skipped":
            badge = "[yellow][SKIP] SKIPPED[/]"
        elif step_res.status == "filtered":
            badge = "[blue][STOP] FILTERED[/]"
        else:
            badge = "[red][ERR] FAILED[/]"

        duration = f"{step_res.duration_ms:.1f}ms"
        
        detail = ""
        if step_res.error:
            detail = f"[red]{step_res.error}[/]"
        elif isinstance(step_res.data, dict):
            # Show a concise summary
            if "status_code" in step_res.data:
                detail = f"HTTP {step_res.data['status_code']} OK"
            elif "stdout" in step_res.data:
                detail = step_res.data['stdout'][:60] + ("..." if len(step_res.data['stdout']) > 60 else "")
            elif "message_id" in step_res.data:
                detail = f"Telegram msg ID {step_res.data['message_id']}"
            elif "recipients" in step_res.data:
                detail = f"Email sent to {', '.join(step_res.data['recipients'])}"
            elif "output" in step_res.data:
                detail = step_res.data['output'][:60] + "..."
            else:
                detail = str(step_res.data)[:60]
        elif step_res.data is not None:
            detail = str(step_res.data)[:60]

        table.add_row(step_id, badge, duration, detail)

    console.print(table)


def print_history_table(runs: List[Dict[str, Any]]):
    """Renders execution history from SQLite."""
    table = Table(title="Recent Workflow Executions", show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Run ID", style="dim", width=10)
    table.add_column("Workflow", style="bold white", width=24)
    table.add_column("Trigger", style="cyan", width=12)
    table.add_column("Status", width=12)
    table.add_column("Duration", justify="right", width=12)
    table.add_column("Timestamp", style="dim")

    for r in runs:
        status_badge = "[green][OK] SUCCESS[/]" if r["status"] == "success" else "[red][ERR] FAILED[/]"
        table.add_row(
            r["run_id"],
            r["workflow_name"],
            r["trigger_type"],
            status_badge,
            f"{r['duration_ms']:.1f}ms",
            r["started_at"].replace("T", " ")[:19]
        )

    console.print(table)
