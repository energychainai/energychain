"""Fail-closed, single-writer SQLite run ledger for READ/ANALYZE tasks.

Not a distributed worker; abandoned reservations require explicit operator reconciliation.
"""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
from threading import RLock
from energychain.intelligence_runtime.contracts import (
    EvidenceRecord, IntelligenceResult, RunConflict, SourceEvidence,
    StepRecord, VerifiedFinding,
)
from energychain.intelligence_runtime.engine import _clean


def _rehydrate(obj):
    steps=tuple(StepRecord(**x) for x in obj.get("steps",[]))
    evidence=tuple(EvidenceRecord(**{**e,"observed_sources":tuple(SourceEvidence(**s) for s in e["observed_sources"]), "parent_evidence_ids":tuple(e.get("parent_evidence_ids",[]))})
                   for e in obj.get("evidence",[]))
    findings=tuple(VerifiedFinding(**x) for x in obj.get("findings",[]))
    return IntelligenceResult(**{**obj,"steps":steps,"evidence":evidence,"findings":findings})


class SQLiteIntelligenceStore:
    """Idempotent completed-run replay; never automatically rerun a stalled execution."""
    def __init__(self,path: str|Path):
        self._db=sqlite3.connect(str(path),check_same_thread=False,timeout=10)
        self._db.execute("PRAGMA busy_timeout=10000")
        self._db.execute("""CREATE TABLE IF NOT EXISTS intelligence_runs (
            run_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            site_id TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('reserved','finished')),
            result TEXT)""")
        self._db.commit()
        self._lock=RLock()

    def reserve(self,run_id:str,principal_id:str,site_id:str,fingerprint:str):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row=self._db.execute("SELECT principal_id,site_id,fingerprint,state,result FROM intelligence_runs WHERE run_id=?",(run_id,)).fetchone()
                if row:
                    if row[:
                        3]!=(principal_id,site_id,fingerprint):
                        raise RunConflict("run id already bound to a different task or scope")
                    if row[3]!="finished":
                        raise RunConflict("run is incomplete; operator reconciliation required")
                    if row[4] is None:
                        raise RunConflict("stored result missing")
                    result=_rehydrate(json.loads(row[4]))
                else:
                    self._db.execute("INSERT INTO intelligence_runs(run_id,principal_id,site_id,fingerprint,state) VALUES(?,?,?,?,?)",
                                     (run_id,principal_id,site_id,fingerprint,"reserved"))
                    result=None
                self._db.commit()
                return result
            except Exception:
                self._db.rollback()
                raise

    def finish(self,result:IntelligenceResult):
        payload=json.dumps(_clean(result),sort_keys=True,allow_nan=False)
        with self._lock,self._db:
            cur=self._db.execute("UPDATE intelligence_runs SET state='finished',result=? WHERE run_id=? AND state='reserved'",
                                 (payload,result.run_id))
            if cur.rowcount!=1:
                raise RunConflict("run reservation is missing or already finished")

    def close(self):
        with self._lock:self._db.close()

    def __enter__(self):return self
    def __exit__(self,*exc):self.close()
