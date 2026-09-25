"""SQLite execution history and persistence ledger."""

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
from neo.core.models import RunResult


class ExecutionLedger:
    """Manages persistent SQLite storage of execution runs and audits."""

    def __init__(self, db_path: str = "neo_ledger.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error TEXT,
                    details_json TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_name ON runs(workflow_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_started_at ON runs(started_at DESC)")
            conn.commit()

    def record_run(self, result: RunResult) -> None:
        """Stores a completed workflow execution."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            details = {
                "trigger_data": result.trigger_data,
                "steps": {k: v.model_dump() for k, v in result.steps.items()}
            }
            cursor.execute("""
                INSERT OR REPLACE INTO runs 
                (run_id, workflow_name, status, trigger_type, started_at, duration_ms, error, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.run_id,
                result.workflow_name,
                result.status,
                result.trigger_type,
                result.started_at.isoformat(),
                result.duration_ms,
                result.error,
                json.dumps(details, default=str)
            ))
            conn.commit()

    def get_recent_runs(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieves recent runs ordered by start time."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
