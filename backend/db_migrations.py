"""Small additive migrations for deployments created by older ZIP builds.

The project doesn't otherwise depend on Alembic. These migrations only add
nullable/backfilled columns and are safe to run repeatedly at startup.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_names(engine: Engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def apply_additive_migrations(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    if "exams" in tables:
        columns = _column_names(engine, "exams")
        with engine.begin() as connection:
            if "status" not in columns:
                connection.execute(text("ALTER TABLE exams ADD COLUMN status VARCHAR(20)"))
                connection.execute(text("UPDATE exams SET status = 'open' WHERE status IS NULL"))
            if "join_code_expires_at" not in columns:
                connection.execute(text("ALTER TABLE exams ADD COLUMN join_code_expires_at TIMESTAMP"))
                connection.execute(
                    text(
                        "UPDATE exams SET join_code_expires_at = :expiry "
                        "WHERE join_code_expires_at IS NULL"
                    ),
                    {"expiry": datetime.now(timezone.utc) + timedelta(hours=24)},
                )
            exam_columns = {
                "candidate_auth_mode": ("VARCHAR(20)", "manual"),
                "exam_url": ("VARCHAR(2048)", None),
                "require_extension": ("BOOLEAN", False),
                "min_extension_version": ("VARCHAR(32)", "1.0.0"),
                "require_fullscreen": ("BOOLEAN", True),
                "require_camera": ("BOOLEAN", True),
                "require_microphone": ("BOOLEAN", False),
                "require_screen_share": ("BOOLEAN", False),
                "block_clipboard": ("BOOLEAN", True),
                "max_focus_loss_seconds": ("FLOAT", 5.0),
                "google_allowed_domain": ("VARCHAR(255)", None),
            }
            for name, (sql_type, default) in exam_columns.items():
                if name in columns:
                    continue
                connection.execute(text(f"ALTER TABLE exams ADD COLUMN {name} {sql_type}"))
                if default is not None:
                    connection.execute(
                        text(f"UPDATE exams SET {name} = :default WHERE {name} IS NULL"),
                        {"default": default},
                    )

    if "exam_sessions" in tables:
        columns = _column_names(engine, "exam_sessions")
        with engine.begin() as connection:
            if "last_seen_at" not in columns:
                connection.execute(text("ALTER TABLE exam_sessions ADD COLUMN last_seen_at TIMESTAMP"))
            if "disconnect_reason" not in columns:
                connection.execute(text("ALTER TABLE exam_sessions ADD COLUMN disconnect_reason VARCHAR(100)"))
            session_columns = {
                "candidate_number": ("VARCHAR(100)", None),
                "candidate_email": ("VARCHAR(255)", None),
                "candidate_identity_id": ("VARCHAR(36)", None),
                "authentication_method": ("VARCHAR(20)", "manual"),
                "client_type": ("VARCHAR(32)", "desktop_cv"),
                "extension_version": ("VARCHAR(32)", None),
                "browser_name": ("VARCHAR(50)", None),
                "device_id_hash": ("VARCHAR(64)", None),
                "integrity_score_current": ("FLOAT", 0.0),
                "integrity_status_current": ("VARCHAR(20)", "healthy"),
                "browser_event_count": ("INTEGER", 0),
            }
            for name, (sql_type, default) in session_columns.items():
                if name in columns:
                    continue
                connection.execute(text(f"ALTER TABLE exam_sessions ADD COLUMN {name} {sql_type}"))
                if default is not None:
                    connection.execute(
                        text(f"UPDATE exam_sessions SET {name} = :default WHERE {name} IS NULL"),
                        {"default": default},
                    )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_exam_candidate_number "
                    "ON exam_sessions (exam_id, candidate_number)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_exam_candidate_identity "
                    "ON exam_sessions (exam_id, candidate_identity_id)"
                )
            )
