"""Convergent additive migrations for deployments created by older builds.

The project does not yet depend on Alembic. Migrations in this module only add
or backfill data, keep the legacy columns during the RBAC transition, and are
safe to run repeatedly at startup. ``schema_migrations`` records completed
milestones for support diagnostics; column/table checks remain the source of
truth so an interrupted deployment can repair itself on the next startup.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_names(engine: Engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def _create_migration_ledger(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version VARCHAR(100) PRIMARY KEY, "
                "applied_at TIMESTAMP NOT NULL"
                ")"
            )
        )


def _record_migration(engine: Engine, version: str) -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": version},
        ).first()
        if exists is None:
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (version, applied_at) "
                    "VALUES (:version, :applied_at)"
                ),
                {"version": version, "applied_at": datetime.now(timezone.utc)},
            )


def _add_columns(
    engine: Engine,
    table_name: str,
    definitions: dict[str, str],
) -> None:
    columns = _column_names(engine, table_name)
    with engine.begin() as connection:
        for name, sql_type in definitions.items():
            if name not in columns:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {name} {sql_type}")
                )


def _backfill_rbac_foundation(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    required = {"organizations", "users", "exams", "organization_memberships", "exam_assignments"}
    if not required.issubset(tables):
        return

    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE organizations SET "
                "status = COALESCE(status, 'active'), "
                "settings_json = COALESCE(settings_json, '{}'), "
                "retention_days = COALESCE(retention_days, 365), "
                "updated_at = COALESCE(updated_at, created_at, :now)"
            ),
            {"now": now},
        )
        organizations = connection.execute(
            text("SELECT id FROM organizations WHERE slug IS NULL OR slug = ''")
        ).mappings()
        for organization in organizations:
            connection.execute(
                text("UPDATE organizations SET slug = :slug WHERE id = :org_id"),
                {
                    "slug": f"org-{str(organization['id']).replace('-', '')[:12]}",
                    "org_id": organization["id"],
                },
            )

        connection.execute(
            text(
                "UPDATE users SET "
                "status = COALESCE(status, 'active'), "
                "session_version = COALESCE(session_version, 1), "
                "updated_at = COALESCE(updated_at, created_at, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "UPDATE exams SET "
                "owner_user_id = COALESCE(owner_user_id, created_by_user_id), "
                "version = COALESCE(version, 1), "
                "updated_at = COALESCE(updated_at, created_at, :now)"
            ),
            {"now": now},
        )

        users = list(
            connection.execute(text("SELECT id, org_id, role FROM users")).mappings()
        )
        for user in users:
            existing = connection.execute(
                text(
                    "SELECT 1 FROM organization_memberships "
                    "WHERE user_id = :user_id AND org_id = :org_id"
                ),
                {"user_id": user["id"], "org_id": user["org_id"]},
            ).first()
            if existing is None:
                membership_role = "org_admin" if user["role"] == "admin" else "exam_manager"
                connection.execute(
                    text(
                        "INSERT INTO organization_memberships "
                        "(id, user_id, org_id, role, status, created_at, updated_at) "
                        "VALUES (:id, :user_id, :org_id, :role, 'active', :now, :now)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": user["id"],
                        "org_id": user["org_id"],
                        "role": membership_role,
                        "now": now,
                    },
                )

        exams = list(
            connection.execute(
                text("SELECT id, org_id, created_by_user_id FROM exams")
            ).mappings()
        )
        for exam in exams:
            creator_assignment = connection.execute(
                text(
                    "SELECT 1 FROM exam_assignments "
                    "WHERE exam_id = :exam_id AND user_id = :user_id"
                ),
                {"exam_id": exam["id"], "user_id": exam["created_by_user_id"]},
            ).first()
            if creator_assignment is None:
                connection.execute(
                    text(
                        "INSERT INTO exam_assignments "
                        "(id, exam_id, user_id, assignment_role, status, "
                        "assigned_by_user_id, is_pinned, created_at, updated_at) "
                        "VALUES (:id, :exam_id, :user_id, 'owner', 'active', "
                        ":user_id, :is_pinned, :now, :now)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "exam_id": exam["id"],
                        "user_id": exam["created_by_user_id"],
                        "is_pinned": False,
                        "now": now,
                    },
                )

            # Legacy proctors could see every exam in their organization. Give
            # them explicit manager assignments so enabling v2 never silently
            # removes existing access. Organization admins do not need one.
            for user in users:
                if user["org_id"] != exam["org_id"] or user["role"] != "proctor":
                    continue
                existing = connection.execute(
                    text(
                        "SELECT 1 FROM exam_assignments "
                        "WHERE exam_id = :exam_id AND user_id = :user_id"
                    ),
                    {"exam_id": exam["id"], "user_id": user["id"]},
                ).first()
                if existing is None:
                    connection.execute(
                        text(
                            "INSERT INTO exam_assignments "
                            "(id, exam_id, user_id, assignment_role, status, "
                            "assigned_by_user_id, is_pinned, created_at, updated_at) "
                            "VALUES (:id, :exam_id, :user_id, 'manager', 'active', "
                            ":assigned_by, :is_pinned, :now, :now)"
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "exam_id": exam["id"],
                            "user_id": user["id"],
                            "assigned_by": exam["created_by_user_id"],
                            "is_pinned": False,
                            "now": now,
                        },
                    )


def apply_additive_migrations(engine: Engine) -> None:
    _create_migration_ledger(engine)
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
                "browser_version": ("VARCHAR(50)", None),
                "platform": ("VARCHAR(100)", None),
                "capabilities_json": ("TEXT", "[]"),
                "device_id_hash": ("VARCHAR(64)", None),
                "camera_status": ("VARCHAR(20)", "unknown"),
                "microphone_status": ("VARCHAR(20)", "unknown"),
                "screen_share_status": ("VARCHAR(20)", "unknown"),
                "reset_count": ("INTEGER", 0),
                "last_reset_at": ("TIMESTAMP", None),
                "last_reset_reason": ("VARCHAR(500)", None),
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

    tables = set(inspect(engine).get_table_names())
    if "access_grants" in tables:
        _add_columns(
            engine,
            "access_grants",
            {"decision_reason": "VARCHAR(500)"},
        )
    if "audit_logs" in tables:
        _add_columns(
            engine,
            "audit_logs",
            {"access_grant_id": "VARCHAR(36)"},
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_audit_logs_access_grant_id "
                    "ON audit_logs (access_grant_id)"
                )
            )

    tables = set(inspect(engine).get_table_names())
    if "organizations" in tables:
        _add_columns(
            engine,
            "organizations",
            {
                "logo_url": "VARCHAR(2048)",
                "address": "VARCHAR(500)",
                "email": "VARCHAR(255)",
                "phone": "VARCHAR(32)",
                "website": "VARCHAR(2048)",
                "slug": "VARCHAR(255)",
                "status": "VARCHAR(20)",
                "settings_json": "TEXT",
                "quota_concurrent_sessions": "INTEGER",
                "retention_days": "INTEGER",
                "updated_at": "TIMESTAMP",
            },
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_organizations_slug "
                    "ON organizations (slug)"
                )
            )

    if "users" in tables:
        _add_columns(
            engine,
            "users",
            {
                "display_name": "VARCHAR(200)",
                "phone": "VARCHAR(32)",
                "avatar_url": "VARCHAR(2048)",
                "status": "VARCHAR(20)",
                "session_version": "INTEGER",
                "locked_at": "TIMESTAMP",
                "mfa_enabled": "BOOLEAN",
                "mfa_secret_encrypted": "TEXT",
                "mfa_recovery_codes_json": "TEXT",
                "google_subject": "VARCHAR(255)",
                "updated_at": "TIMESTAMP",
            },
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_subject "
                    "ON users (google_subject)"
                )
            )

    if "exams" in tables:
        _add_columns(
            engine,
            "exams",
            {
                "owner_user_id": "VARCHAR(36)",
                "scheduled_start_at": "TIMESTAMP",
                "scheduled_end_at": "TIMESTAMP",
                "archived_at": "TIMESTAMP",
                "version": "INTEGER",
                "updated_at": "TIMESTAMP",
            },
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exams_owner_user_id "
                    "ON exams (owner_user_id)"
                )
            )

    if "exam_assignments" in tables:
        _add_columns(
            engine,
            "exam_assignments",
            {
                "is_pinned": "BOOLEAN",
                "pinned_at": "TIMESTAMP",
            },
        )

    _backfill_rbac_foundation(engine)
    if "exam_assignments" in set(inspect(engine).get_table_names()):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE exam_assignments "
                    "SET is_pinned = COALESCE(is_pinned, :not_pinned)"
                ),
                {"not_pinned": False},
            )
    if "users" in set(inspect(engine).get_table_names()):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE users SET mfa_enabled = COALESCE(mfa_enabled, :disabled)"),
                {"disabled": False},
            )
    _record_migration(engine, "2026_08_03_rbac_foundation")
    _record_migration(engine, "2026_08_09_web_google_auth")
    _record_migration(engine, "2026_08_11_exam_assignment_pins")
