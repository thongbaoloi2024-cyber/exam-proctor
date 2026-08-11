"""Platform and organization policy resolution for exam configuration.

Frontend defaults improve usability, but the backend is the only enforcement
point.  Effective exam policy is resolved in this order:

    platform security floor -> organization policy -> explicit exam override

An override may make a setting stricter, never weaker than the effective
organization floor.
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from . import models

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"
)
_BOOLEAN_FLOOR_FIELDS = (
    "require_extension",
    "require_fullscreen",
    "require_camera",
    "require_microphone",
    "require_screen_share",
    "block_clipboard",
)
EXAM_POLICY_FIELDS = (
    "candidate_auth_mode",
    "min_extension_version",
    *_BOOLEAN_FLOOR_FIELDS,
    "max_focus_loss_seconds",
)


def version_tuple(value: str) -> tuple[int, int, int]:
    match = _SEMVER_RE.fullmatch(value)
    if match is None:
        raise ValueError("Phien ban extension phai co dang MAJOR.MINOR.PATCH")
    return tuple(int(match.group(index)) for index in (1, 2, 3))


def stricter_version(left: str, right: str) -> str:
    return left if version_tuple(left) >= version_tuple(right) else right


class PlatformPolicy(BaseModel):
    min_extension_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$",
    )
    require_extension: bool = False
    require_fullscreen: bool = False
    require_camera: bool = False
    require_microphone: bool = False
    require_screen_share: bool = False
    block_clipboard: bool = False
    max_focus_loss_seconds: float = Field(default=300.0, ge=0.0, le=300.0)
    min_retention_days: int = Field(default=1, ge=1, le=3650)
    max_retention_days: int = Field(default=3650, ge=1, le=3650)

    @model_validator(mode="after")
    def valid_retention_range(self) -> "PlatformPolicy":
        if self.max_retention_days < self.min_retention_days:
            raise ValueError("Retention toi da phai lon hon hoac bang retention toi thieu")
        return self


class OrganizationPolicy(BaseModel):
    default_candidate_auth_mode: Literal["manual", "google"] = "manual"
    min_extension_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$",
    )
    require_extension: bool = False
    require_fullscreen: bool = True
    require_camera: bool = True
    require_microphone: bool = False
    require_screen_share: bool = False
    block_clipboard: bool = True
    max_focus_loss_seconds: float = Field(default=5.0, ge=0.0, le=300.0)
    retention_days: int = Field(default=365, ge=1, le=3650)

    @model_validator(mode="after")
    def coherent_defaults(self) -> "OrganizationPolicy":
        if self.default_candidate_auth_mode == "google" and not self.require_extension:
            raise ValueError("Che do Google mac dinh bat buoc su dung browser extension")
        return self


class ResolvedExamPolicy(BaseModel):
    candidate_auth_mode: Literal["manual", "google"]
    min_extension_version: str
    require_extension: bool
    require_fullscreen: bool
    require_camera: bool
    require_microphone: bool
    require_screen_share: bool
    block_clipboard: bool
    max_focus_loss_seconds: float


def get_platform_policy(db: Session) -> PlatformPolicy:
    stored = db.get(models.PlatformPolicySetting, "default")
    if stored is None:
        return PlatformPolicy()
    try:
        payload = json.loads(stored.settings_json or "{}")
    except (TypeError, ValueError):
        payload = {}
    return PlatformPolicy.model_validate(payload)


def get_stored_organization_policy(
    organization: models.Organization,
) -> OrganizationPolicy:
    try:
        payload = json.loads(organization.settings_json or "{}")
    except (TypeError, ValueError):
        payload = {}
    payload.setdefault("retention_days", organization.retention_days)
    return OrganizationPolicy.model_validate(payload)


def validate_organization_policy(
    policy: OrganizationPolicy,
    platform: PlatformPolicy,
) -> None:
    if version_tuple(policy.min_extension_version) < version_tuple(
        platform.min_extension_version
    ):
        raise ValueError(
            f"Phien ban extension toi thieu khong duoc thap hon {platform.min_extension_version}"
        )
    for field_name in _BOOLEAN_FLOOR_FIELDS:
        if getattr(platform, field_name) and not getattr(policy, field_name):
            raise ValueError(f"Chinh sach to chuc khong duoc tat {field_name}")
    if policy.max_focus_loss_seconds > platform.max_focus_loss_seconds:
        raise ValueError(
            "Thoi gian roi cua so khong duoc lon hon muc san cua he thong"
        )
    if not platform.min_retention_days <= policy.retention_days <= platform.max_retention_days:
        raise ValueError("Retention nam ngoai khoang cho phep cua he thong")


def get_effective_organization_policy(
    db: Session,
    organization: models.Organization,
) -> OrganizationPolicy:
    policy = get_stored_organization_policy(organization)
    platform = get_platform_policy(db)
    updates: dict[str, Any] = {
        "min_extension_version": stricter_version(
            policy.min_extension_version,
            platform.min_extension_version,
        ),
        "max_focus_loss_seconds": min(
            policy.max_focus_loss_seconds,
            platform.max_focus_loss_seconds,
        ),
        "retention_days": min(
            max(policy.retention_days, platform.min_retention_days),
            platform.max_retention_days,
        ),
    }
    for field_name in _BOOLEAN_FLOOR_FIELDS:
        updates[field_name] = getattr(policy, field_name) or getattr(platform, field_name)
    if policy.default_candidate_auth_mode == "google":
        updates["require_extension"] = True
    return policy.model_copy(update=updates)


def resolve_exam_policy(
    db: Session,
    organization: models.Organization,
    overrides: Mapping[str, Any] | None = None,
) -> ResolvedExamPolicy:
    organization_policy = get_effective_organization_policy(db, organization)
    requested = dict(overrides or {})
    values: dict[str, Any] = {
        "candidate_auth_mode": organization_policy.default_candidate_auth_mode,
        **{
            field_name: getattr(organization_policy, field_name)
            for field_name in EXAM_POLICY_FIELDS
            if field_name != "candidate_auth_mode"
        },
    }
    values.update({key: value for key, value in requested.items() if key in EXAM_POLICY_FIELDS})

    if version_tuple(values["min_extension_version"]) < version_tuple(
        organization_policy.min_extension_version
    ):
        raise ValueError(
            "Phien ban extension cua ky thi thap hon chinh sach to chuc"
        )
    for field_name in _BOOLEAN_FLOOR_FIELDS:
        if getattr(organization_policy, field_name) and not values[field_name]:
            raise ValueError(f"Ky thi khong duoc tat {field_name} bat buoc")
    if values["max_focus_loss_seconds"] > organization_policy.max_focus_loss_seconds:
        raise ValueError(
            "Thoi gian roi cua so cua ky thi vuot chinh sach to chuc"
        )
    if values["candidate_auth_mode"] == "google" and not values["require_extension"]:
        raise ValueError("Che do Google bat buoc su dung browser extension")
    return ResolvedExamPolicy.model_validate(values)


def exam_policy_values(exam: models.Exam) -> dict[str, Any]:
    return {field_name: getattr(exam, field_name) for field_name in EXAM_POLICY_FIELDS}
