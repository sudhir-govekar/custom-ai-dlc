import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "./data/ai_dlc.db"))


def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def initialize():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                service TEXT NOT NULL,
                requirement TEXT NOT NULL,
                artifacts_json TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer TEXT,
                decision_comment TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def create_workflow(request, artifacts):
    workflow_id = str(uuid4())
    timestamp = utc_now()

    with connect() as db:
        db.execute("""
            INSERT INTO workflows (
                id, project, service, requirement, artifacts_json,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            workflow_id,
            request.project,
            request.service,
            request.requirement,
            json.dumps(artifacts),
            "pending_approval",
            timestamp,
            timestamp,
        ))

    return get_workflow(workflow_id)


def get_workflow(workflow_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM workflows WHERE id = ?",
            (workflow_id,),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    result["artifacts"] = json.loads(result.pop("artifacts_json"))
    return result


def ensure_construction_columns():
    """Safe migration for existing SQLite databases."""
    with connect() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(workflows)")
        }

        migrations = {
            "construction_json": "TEXT",
            "construction_status": (
                "TEXT NOT NULL DEFAULT 'not_started'"
            ),
            "construction_error": "TEXT",
        }

        for column, sql_type in migrations.items():
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE workflows "
                    f"ADD COLUMN {column} {sql_type}"
                )


def save_construction_result(
    workflow_id: str,
    plan: dict,
):
    with connect() as conn:
        cursor = conn.execute(
            """
            UPDATE workflows
            SET construction_json = ?,
                construction_status = 'completed',
                construction_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'approved'
            """,
            (json.dumps(plan), workflow_id),
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Workflow not found or not approved; "
                "Construction result was not saved."
            )


def mark_construction_started(workflow_id: str):
    with connect() as conn:
        cursor = conn.execute(
            """
            UPDATE workflows
            SET construction_status = 'in_progress',
                construction_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'approved'
              AND construction_status IN ('not_started', 'failed')
            """,
            (workflow_id,),
        )

        return cursor.rowcount == 1


def mark_construction_failed(
    workflow_id: str,
    error_message: str,
):
    # Do not store credentials or full request headers in this field.
    with connect() as conn:
        conn.execute(
            """
            UPDATE workflows
            SET construction_status = 'failed',
                construction_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (error_message[:1000], workflow_id),
        )


def list_workflows():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                project,
                service,
                requirement,
                artifacts_json,
                status,
                reviewer,
                decision_comment,
                created_at,
                updated_at,
                construction_json,
                construction_status,
                construction_error
            FROM workflows
            ORDER BY created_at DESC
            """
        ).fetchall()

    workflows = []

    for row in rows:
        workflow = dict(row)

        # Parse saved Inception artifacts.
        try:
            workflow["artifacts"] = json.loads(
                workflow.get("artifacts_json") or "{}"
            )
        except (json.JSONDecodeError, TypeError):
            workflow["artifacts"] = {}

        # Parse the saved Construction plan.
        try:
            workflow["construction"] = json.loads(
                workflow.get("construction_json") or "{}"
            )
        except (json.JSONDecodeError, TypeError):
            workflow["construction"] = {}

        workflows.append(workflow)

    return workflows
def record_decision(workflow_id, decision, reviewer, comment):
    status = "approved" if decision == "approve" else "rejected"

    with connect() as db:
        cursor = db.execute("""
            UPDATE workflows
            SET status = ?, reviewer = ?,
                decision_comment = ?, updated_at = ?
            WHERE id = ? AND status = 'pending_approval'
        """, (
            status,
            reviewer,
            comment,
            utc_now(),
            workflow_id,
        ))

    if cursor.rowcount != 1:
        return None

    return get_workflow(workflow_id)