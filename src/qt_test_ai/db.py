from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .models import Finding, TestRun


def open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            project_root TEXT NOT NULL,
            exe_path TEXT,
            meta_json TEXT NOT NULL,
            findings_json TEXT NOT NULL,
            total_findings INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            warning_count INTEGER DEFAULT 0
        );
        """
    )
    
    # Auto-migration: check if columns exist, if not add them
    try:
        conn.execute("SELECT total_findings FROM test_runs LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE test_runs ADD COLUMN total_findings INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE test_runs ADD COLUMN error_count INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE test_runs ADD COLUMN warning_count INTEGER DEFAULT 0")
        
    return conn


def save_run(conn: sqlite3.Connection, run: TestRun) -> int:
    findings_json = json.dumps([asdict(f) for f in run.findings], ensure_ascii=False)
    meta_json = json.dumps(run.meta, ensure_ascii=False)
    
    # Calculate stats
    total = len(run.findings)
    err = sum(1 for f in run.findings if f.severity == "error")
    warn = sum(1 for f in run.findings if f.severity == "warning")
    
    cur = conn.execute(
        """
        INSERT INTO test_runs(
            created_at, project_root, exe_path, meta_json, findings_json,
            total_findings, error_count, warning_count
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            run.created_at.isoformat(timespec="seconds"),
            run.project_root,
            run.exe_path,
            meta_json,
            findings_json,
            total,
            err,
            warn
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_runs(conn: sqlite3.Connection, limit: int = 50) -> list[tuple[int, datetime, str, str | None]]:
    rows = conn.execute(
        "SELECT id, created_at, project_root, exe_path FROM test_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for rid, created_at, project_root, exe_path in rows:
        out.append((int(rid), datetime.fromisoformat(created_at), project_root, exe_path))
    return out


def load_run(conn: sqlite3.Connection, run_id: int) -> TestRun:
    row = conn.execute(
        "SELECT created_at, project_root, exe_path, meta_json, findings_json FROM test_runs WHERE id=?",
        (run_id,),
    ).fetchone()
    if not row:
        raise KeyError(f"run_id not found: {run_id}")
    created_at_s, project_root, exe_path, meta_json, findings_json = row
    findings_raw = json.loads(findings_json)
    findings = [Finding(**fr) for fr in findings_raw]
    meta = json.loads(meta_json)
    return TestRun(
        project_root=project_root,
        exe_path=exe_path,
        created_at=datetime.fromisoformat(created_at_s),
        findings=findings,
        meta=meta,
    )


def delete_run(conn: sqlite3.Connection, run_id: int) -> bool:
    """Delete a test run by ID. Returns True if deleted, False if not found."""
    cur = conn.execute("DELETE FROM test_runs WHERE id=?", (run_id,))
    conn.commit()
    return cur.rowcount > 0
