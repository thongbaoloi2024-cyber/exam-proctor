"""Provision a System Admin without exposing a public registration endpoint.

Usage:
    set SYSTEM_ADMIN_BOOTSTRAP_PASSWORD=<strong password>
    python scripts/bootstrap_system_admin.py --email admin@example.com

If the email already belongs to a platform user, the script only adds the
system role. The operation is idempotent.
"""
from __future__ import annotations

import argparse
import getpass
import os

from backend import models
from backend.auth import hash_password
from backend.db import Base, SessionLocal, engine
from backend.db_migrations import apply_additive_migrations


def _password() -> str:
    value = os.environ.get("SYSTEM_ADMIN_BOOTSTRAP_PASSWORD")
    if value is None:
        value = getpass.getpass("System Admin password: ")
    if len(value) < 12 or len(value.encode("utf-8")) > 72:
        raise SystemExit("Password must contain 12-72 UTF-8 bytes")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision one System Admin")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    email = args.email.strip().casefold()
    if "@" not in email:
        raise SystemExit("Invalid email")

    Base.metadata.create_all(bind=engine)
    apply_additive_migrations(engine)
    with SessionLocal() as db:
        system_org = db.query(models.Organization).filter_by(slug="system").first()
        if system_org is None:
            system_org = models.Organization(
                name="DATT System",
                slug="system",
                status="active",
                settings_json='{"system_tenant": true}',
            )
            db.add(system_org)
            db.flush()
        elif system_org.status != "active":
            # The internal identity tenant must never inherit a customer-tenant
            # suspension. This also provides a recovery path for older installs.
            system_org.status = "active"

        user = db.query(models.User).filter_by(email=email).first()
        created_user = user is None
        if user is None:
            user = models.User(
                org_id=system_org.id,
                email=email,
                password_hash=hash_password(_password()),
                role="admin",
                status="active",
            )
            db.add(user)
            db.flush()
            db.add(
                models.OrganizationMembership(
                    user_id=user.id,
                    org_id=system_org.id,
                    role="org_admin",
                    status="active",
                )
            )
        else:
            # Keep the former customer membership, but use the dedicated
            # internal tenant as the active identity context for System Admin.
            membership = db.query(models.OrganizationMembership).filter_by(
                user_id=user.id,
                org_id=system_org.id,
            ).first()
            if membership is None:
                db.add(
                    models.OrganizationMembership(
                        user_id=user.id,
                        org_id=system_org.id,
                        role="org_admin",
                        status="active",
                    )
                )
            else:
                membership.role = "org_admin"
                membership.status = "active"
            user.org_id = system_org.id
            user.role = "admin"

        system_role = db.query(models.SystemRole).filter_by(
            user_id=user.id,
            role="system_admin",
        ).first()
        if system_role is None:
            system_role = models.SystemRole(
                user_id=user.id,
                role="system_admin",
                status="active" if user.mfa_enabled else "pending_mfa",
            )
            db.add(system_role)
        else:
            system_role.status = "active" if user.mfa_enabled else "pending_mfa"
        user.status = "active"
        user.session_version += 1
        db.commit()
        action = "created" if created_user else "updated"
        suffix = "" if user.mfa_enabled else " Complete MFA setup at /ui/mfa."
        print(f"System Admin {action}: {email}.{suffix}")


if __name__ == "__main__":
    main()
