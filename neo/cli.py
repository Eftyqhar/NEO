"""Unified Typer CLI entrypoint for Neo workflow automation engine."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.live import Live

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from neo import __version__
from neo.core.models import RunResult
from neo.core.runner import WorkflowRunner
from neo.core.ledger import ExecutionLedger
from neo.ui.console import print_banner, print_run_result, print_history_table
from neo.ui.dashboard import DaemonDashboard
from neo.generator.ai_builder import generate_workflow_yaml

app = typer.Typer(
    name="neo",
    help="Neo: Lightweight Real-Time CLI Workflow Automation Engine",
    add_completion=False
)
console = Console()


@app.command()
def run(
    workflow_file: str = typer.Argument(..., help="Path to YAML workflow file"),
    trigger_json: Optional[str] = typer.Option(None, "--trigger-json", "-t", help="Raw JSON string for trigger payload"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full debug JSON data")
):
    """Executes a workflow pipeline immediately in manual mode."""
    if not os.path.exists(workflow_file):
        console.print(f"[red]Error: Workflow file '{workflow_file}' not found.[/]")
        raise typer.Exit(code=1)

    runner = WorkflowRunner()
    try:
        wf = runner.load_workflow_file(workflow_file)
    except Exception as e:
        console.print(f"[red]Error parsing workflow:[/red] {e}")
        raise typer.Exit(code=1)

    trigger_data = {}
    if trigger_json:
        try:
            trigger_data = json.loads(trigger_json)
        except Exception as e:
            console.print(f"[red]Invalid --trigger-json payload:[/red] {e}")
            raise typer.Exit(code=1)
    else:
        # Default mock trigger payload
        trigger_data = {"trigger_type": "manual", "source": "cli"}

    with console.status(f"[cyan]Executing pipeline for '[bold white]{wf.name}[/]'...", spinner="dots"):
        result = asyncio.run(runner.execute_workflow(wf, trigger_data))

    print_run_result(result)

    if verbose and result.status == "success":
        console.print_json(data=result.model_dump(mode="json"))


@app.command()
def test(
    workflow_file: str = typer.Argument(..., help="Path to YAML workflow file"),
    mock: Optional[str] = typer.Option(None, "--mock", "-m", help="Synthetic mock trigger JSON payload")
):
    """Dry-runs a workflow step-by-step with mock trigger data."""
    run(workflow_file, trigger_json=mock, verbose=True)


@app.command()
def start(
    dir_path: str = typer.Option("./workflows", "--dir", "-d", help="Directory containing workflow YAML files")
):
    """Starts the real-time background daemon with an interactive live TUI dashboard."""
    print_banner()

    runner = WorkflowRunner()
    dashboard = DaemonDashboard(console=console)

    workflows = runner.load_workflows_from_dir(dir_path)
    if not workflows:
        console.print(f"[yellow]No workflow files found in '{dir_path}'.[/]")
        console.print("Create a workflow file in ./workflows/ or run: [cyan]neo create \"<prompt>\"[/]")
        raise typer.Exit(code=0)

    for wf in workflows:
        if wf.enabled:
            dashboard.set_listener(wf.name, f"{wf.trigger.type.upper()}")

    runner.on_run_complete = lambda res: dashboard.add_run(res)

    async def main_loop():
        await runner.start_daemon(dir_path)
        with Live(dashboard.generate_view(), refresh_per_second=2, console=console) as live:
            try:
                while True:
                    await asyncio.sleep(0.5)
                    live.update(dashboard.generate_view())
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            finally:
                await runner.stop_daemon()

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Neo Daemon stopped by user.[/]")


@app.command()
def history(
    limit: int = typer.Option(15, "--limit", "-l", help="Number of recent executions to show")
):
    """Displays the persistent SQLite execution history and run status."""
    ledger = ExecutionLedger()
    runs = ledger.get_recent_runs(limit=limit)
    if not runs:
        console.print("[dim]No past executions recorded in neo_ledger.db yet.[/]")
        return
    print_history_table(runs)


@app.command()
def create(
    prompt: str = typer.Argument(..., help="Natural language description of what the workflow should do"),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="Output path for the generated YAML file")
):
    """Generates a validated YAML workflow from natural language using AI."""
    with console.status("[cyan]Generating workflow with AI...", spinner="aesthetic"):
        try:
            yaml_content = generate_workflow_yaml(prompt)
        except Exception as e:
            console.print(f"[red]Error generating workflow:[/red] {e}")
            raise typer.Exit(code=1)

    out_file = out or f"./workflows/{prompt.lower().replace(' ', '_')[:30]}.yaml"
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    console.print(f"[green]✔ Workflow created successfully at:[/] [bold cyan]{out_file}[/]")
    console.print(Panel(yaml_content, title=f"Generated: {out_file}", border_style="green"))


@app.command()
def version():
    """Prints version and engine information."""
    print_banner()
    console.print(f"Neo Engine Version: [bold cyan]{__version__}[/]")


def main():
    app()


if __name__ == "__main__":
    main()
