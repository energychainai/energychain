"""SQLite step checkpointing for repeatable, observation-only workflows.

No physical execution or mutation tools can run in this workflow. SQLite is single-instance,
not a distributed task engine; use an external scheduler and durable queue for production.
"""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import sqlite3
from pathlib import Path
from energychain.exceptions import PermissionDenied, ValidationError
from energychain.security import Permission, Principal
from energychain.tools import ToolRegistry
from energychain.workflows import WorkflowStep, WorkflowResult


def _json_default(o: object):
    if is_dataclass(o):
        return asdict(o)
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"workflow output is not JSON serializable: {type(o).__name__}")


class SQLiteWorkflowCheckpoints:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute("""CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, site TEXT NOT NULL, principal TEXT NOT NULL,
            fingerprint TEXT NOT NULL, next_step INTEGER NOT NULL,
            outputs TEXT NOT NULL, completed INTEGER NOT NULL)""")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def run(self, run_id: str, tools: ToolRegistry, steps: list[WorkflowStep],
            principal: Principal, site_id: str) -> WorkflowResult:
        if not run_id or len(run_id) > 128 or not steps:
            raise ValidationError("valid run ID and steps required")
        specs = {s["name"]: s for s in tools.describe()}
        for step in steps:
            if step.tool_name not in specs or specs[step.tool_name]["permission"] not in (
                    Permission.READ.value, Permission.ANALYZE.value):
                raise PermissionDenied("durable workflows permit read and analysis tools only")
        try:
            payload = json.dumps([(s.tool_name, s.arguments) for s in steps],
                                 sort_keys=True, default=_json_default, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ValidationError("workflow steps must have JSON arguments") from exc
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        row = self.db.execute("SELECT site,principal,fingerprint,next_step,outputs,completed FROM runs WHERE run_id=?",
                              (run_id,)).fetchone()
        if row:
            old_site, old_principal, old_fingerprint, index, saved, completed = row
            if (old_site, old_principal, old_fingerprint) != (site_id, principal.id, fingerprint):
                raise PermissionDenied("workflow run identifier is already bound to another scope or plan")
            outputs = json.loads(saved)
            if completed:
                return WorkflowResult(True, tuple(outputs))
        else:
            # Validate access even if no tools run due to an unexpected crash.
            tools.policy.authorize(principal, site_id, Permission.READ)
            index, outputs = 0, []
            with self.db:
                self.db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,0)",
                                (run_id, site_id, principal.id, fingerprint, 0, "[]"))
        for n in range(index, len(steps)):
            step = steps[n]
            try:
                result = tools.invoke(step.tool_name, principal, site_id, arguments=step.arguments)
                # Persist only JSON primitives, with typed dataclasses flattened explicitly.
                serialized = json.loads(json.dumps(result, default=_json_default, allow_nan=False))
                outputs.append(serialized)
                with self.db:
                    self.db.execute("UPDATE runs SET next_step=?,outputs=?,completed=? WHERE run_id=?",
                                    (n+1, json.dumps(outputs), int(n+1 == len(steps)), run_id))
            except Exception as exc:
                return WorkflowResult(False, tuple(outputs), n, type(exc).__name__)
        return WorkflowResult(True, tuple(outputs))

    def __enter__(self) -> "SQLiteWorkflowCheckpoints":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
