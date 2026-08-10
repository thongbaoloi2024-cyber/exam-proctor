"""Compatibility and backfill tests for the RBAC v2 database foundation."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from backend import models
from backend.db import Base, SessionLocal
from backend.db_migrations import apply_additive_migrations


def _register(client, *, email: str, organization: str = "RBAC Org") -> str:
    response = client.post(
        "/auth/register",
        json={
            "organization_name": organization,
            "admin_email": email,
            "admin_password": "matkhau123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_legacy_auth_and_exam_writes_new_scope_tables(client):
    admin_token = _register(client, email="foundation-admin@test.local")
    headers = {"Authorization": f"Bearer {admin_token}"}
    created_proctor = client.post(
        "/auth/proctors",
        json={"email": "foundation-proctor@test.local", "password": "matkhau123"},
        headers=headers,
    )
    assert created_proctor.status_code == 201
    proctor_login = client.post(
        "/auth/login",
        json={"email": "foundation-proctor@test.local", "password": "matkhau123"},
    )
    assert proctor_login.status_code == 200
    created_exam = client.post(
        "/exams",
        json={"name": "RBAC Foundation Exam"},
        headers={"Authorization": f"Bearer {proctor_login.json()['access_token']}"},
    )
    assert created_exam.status_code == 201

    with SessionLocal() as db:
        admin = db.query(models.User).filter_by(email="foundation-admin@test.local").one()
        proctor = db.query(models.User).filter_by(email="foundation-proctor@test.local").one()
        organization = db.get(models.Organization, admin.org_id)
        assert organization is not None
        assert organization.slug and organization.slug.startswith("org-")
        assert organization.status == "active"

        admin_membership = db.query(models.OrganizationMembership).filter_by(
            user_id=admin.id,
            org_id=admin.org_id,
        ).one()
        assert admin_membership.role == "org_admin"
        assert admin_membership.status == "active"

        proctor_membership = db.query(models.OrganizationMembership).filter_by(
            user_id=proctor.id,
            org_id=proctor.org_id,
        ).one()
        assert proctor_membership.role == "exam_manager"
        assert proctor_membership.invited_by_user_id == admin.id

        exam = db.get(models.Exam, created_exam.json()["id"])
        assert exam is not None
        assert exam.owner_user_id == proctor.id
        assignment = db.query(models.ExamAssignment).filter_by(
            exam_id=exam.id,
            user_id=proctor.id,
        ).one()
        assert assignment.assignment_role == "owner"
        assert assignment.status == "active"


def test_rbac_migration_backfills_legacy_database_idempotently(tmp_path):
    database_path = (tmp_path / "legacy-rbac.db").as_posix()
    legacy_engine = create_engine(f"sqlite:///{database_path}")
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE organizations ("
                "id VARCHAR(36) PRIMARY KEY, name VARCHAR(200) NOT NULL, created_at TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id VARCHAR(36) PRIMARY KEY, org_id VARCHAR(36) NOT NULL, "
                "email VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL, "
                "role VARCHAR(20) NOT NULL, created_at TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE exams ("
                "id VARCHAR(36) PRIMARY KEY, org_id VARCHAR(36) NOT NULL, "
                "name VARCHAR(200) NOT NULL, join_code VARCHAR(12) NOT NULL, "
                "created_by_user_id VARCHAR(36) NOT NULL, created_at TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO organizations (id, name, created_at) "
                "VALUES ('org-legacy', 'Legacy Org', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, org_id, email, password_hash, role, created_at) VALUES "
                "('admin-legacy', 'org-legacy', 'admin@legacy.local', 'hash', 'admin', CURRENT_TIMESTAMP), "
                "('owner-legacy', 'org-legacy', 'owner@legacy.local', 'hash', 'proctor', CURRENT_TIMESTAMP), "
                "('manager-legacy', 'org-legacy', 'manager@legacy.local', 'hash', 'proctor', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO exams "
                "(id, org_id, name, join_code, created_by_user_id, created_at) "
                "VALUES ('exam-legacy', 'org-legacy', 'Legacy Exam', 'ABC123', "
                "'owner-legacy', CURRENT_TIMESTAMP)"
            )
        )

    # Startup creates new tables, while the migration adds columns to legacy
    # tables and backfills scope rows. Running it twice must not duplicate data.
    Base.metadata.create_all(bind=legacy_engine)
    apply_additive_migrations(legacy_engine)
    apply_additive_migrations(legacy_engine)

    inspector = inspect(legacy_engine)
    assert {"slug", "status", "retention_days"}.issubset(
        {column["name"] for column in inspector.get_columns("organizations")}
    )
    assert {"status", "session_version", "google_subject"}.issubset(
        {column["name"] for column in inspector.get_columns("users")}
    )
    assert {"web_auth_challenges", "web_oauth_transactions"}.issubset(
        set(inspector.get_table_names())
    )
    assert {"owner_user_id", "version"}.issubset(
        {column["name"] for column in inspector.get_columns("exams")}
    )

    with Session(legacy_engine) as db:
        memberships = db.query(models.OrganizationMembership).all()
        assert {(item.user_id, item.role) for item in memberships} == {
            ("admin-legacy", "org_admin"),
            ("owner-legacy", "exam_manager"),
            ("manager-legacy", "exam_manager"),
        }
        assignments = db.query(models.ExamAssignment).all()
        assert {(item.user_id, item.assignment_role) for item in assignments} == {
            ("owner-legacy", "owner"),
            ("manager-legacy", "manager"),
        }
        migration_count = db.execute(
            text(
                "SELECT COUNT(*) FROM schema_migrations "
                "WHERE version = '2026_08_03_rbac_foundation'"
            )
        ).scalar_one()
        assert migration_count == 1

    legacy_engine.dispose()
