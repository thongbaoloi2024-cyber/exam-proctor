"""Smoke tests for the role-aware administration pages."""
from __future__ import annotations


def test_new_admin_page_shells_and_scripts_are_served(client):
    pages = {
        "/ui/system": "/static/system.js",
        "/ui/system/organizations": "/static/system-organizations.js",
        "/ui/system/organizations/org-id": "/static/system-organization-detail.js",
        "/ui/system/security": "/static/system-security.js",
        "/ui/system/evidence": "/static/exams.js",
        "/ui/system/audit": "/static/system-audit.js",
        "/ui/organization/overview": "/static/organization-overview.js",
        "/ui/organization": "/static/organization.js",
        "/ui/organization/settings": "/static/organization-settings.js",
        "/ui/organization/policy": "/static/organization.js",
        "/ui/organization/break-glass": "/static/organization.js",
        "/ui/organization/audit": "/static/organization.js",
        "/ui/exams/overview": "/static/exam-overview.js",
        "/ui/settings": "/static/account-settings.js",
        "/ui/mfa": "/static/mfa.js",
        "/ui/mfa/verify": "/static/mfa-verify.js",
        "/ui/register/organization": "/static/register-organization.js",
        "/ui/exams/exam-id/manage": "/static/exam_manage.js",
    }
    for path, script in pages.items():
        response = client.get(path)
        assert response.status_code == 200
        assert script in response.text
        assert "innerHTML" not in client.get(script).text

    shared_system_script = client.get("/static/system-common.js")
    assert shared_system_script.status_code == 200
    assert "innerHTML" not in shared_system_script.text
    login_script = client.get("/static/login.js").text
    assert 'body.role === "system_admin"' in login_script
    assert '? "/ui/organization/overview"' in login_script

    login_page = client.get("/ui/login").text
    register_page = client.get("/ui/register").text
    assert "/static/style.css?v=" in login_page
    assert "/static/login.js?v=" in login_page
    assert "/static/register.js?v=" in register_page
    assert '<svg width="20" height="20" viewBox="0 0 24 24"' in login_page
    assert '<svg width="20" height="20" viewBox="0 0 24 24"' in register_page


def test_system_admin_sidebar_has_control_panel_navigation_and_account(client):
    response = client.get("/ui/system")
    assert response.status_code == 200
    assert 'id="sidebar-home-link"' in response.text
    assert 'id="system-platform-badge"' in response.text
    assert 'class="system-nav-section"' in response.text
    assert 'id="nav-system-organizations"' in response.text
    assert 'id="nav-system-security"' in response.text
    assert 'id="nav-system-evidence"' in response.text
    assert 'id="nav-system-audit"' in response.text
    assert 'id="system-scope"' in response.text
    assert 'id="sidebar-account"' in response.text
    assert 'id="account-email"' in response.text
    assert 'id="account-settings-button"' in response.text
    assert response.text.index('id="account-settings-button"') < response.text.index('id="logout-btn"')
    assert 'class="page-footer"' in response.text

    api_script = client.get("/static/api.js").text
    assert 'document.body.classList.toggle("has-system-sidebar", isSystemAdmin)' in api_script
    assert 'isOrganizationAdmin ? "/ui/organization/overview" : "/ui/exams/overview"' in api_script


def test_tenant_sidebars_are_role_aware_and_capability_scoped(client):
    response = client.get("/ui/exams")
    assert response.status_code == 200
    assert 'id="tenant-nav-group"' in response.text
    assert 'id="exam-nav-section"' in response.text
    assert 'id="nav-exam-overview"' in response.text
    assert 'id="exam-nav-expandable"' in response.text
    assert 'id="pinned-exams-toggle"' in response.text
    assert 'id="pinned-exams-list"' in response.text
    assert 'id="organization-nav-section"' in response.text
    assert 'id="nav-organization-overview"' in response.text
    assert 'id="organization-platform-badge"' in response.text
    assert 'id="exam-platform-badge"' in response.text
    assert 'id="organization-context"' in response.text
    assert 'id="organization-switcher"' in response.text
    assert '<!-- <div id="organization-context">' not in response.text
    assert "Vận hành kỳ thi" in response.text
    assert "Quản trị tổ chức" in response.text

    api_script = client.get("/static/api.js").text
    assert 'document.body.classList.toggle("has-role-sidebar", isAuthenticated)' in api_script
    assert 'document.body.classList.toggle("has-organization-sidebar", isOrganizationAdmin)' in api_script
    assert 'document.body.classList.toggle("has-exam-manager-sidebar", isExamManager)' in api_script
    assert "const canUseExams = !isOrganizationAdmin" in api_script
    assert 'this.hasCapability("org.members.read")' in api_script
    assert 'this.hasCapability("exam.read") || this.hasCapability("exam.create")' in api_script
    assert 'this.loadOrganizationSwitcher()' in api_script
    assert 'this.loadPinnedExams()' in api_script
    assert "async setExamPinned(examId, isPinned)" in api_script

    stylesheet = client.get("/static/style.css").text
    assert ".has-organization-sidebar" in stylesheet
    assert ".has-exam-manager-sidebar" in stylesheet
    assert "--sidebar-accent-rgb" in stylesheet
    assert ".pinned-exams-list" in stylesheet
    assert ".exam-pin-button" in stylesheet
    exams_script = client.get("/static/exams.js").text
    assert 'currentUser.effective_role === "org_admin"' in exams_script
    assert 'window.location.replace("/ui/organization/overview")' in exams_script
    mfa_page = client.get("/ui/mfa").text
    assert 'id="mfa-qr"' in mfa_page
    assert "qr_code_data_url" in client.get("/static/mfa.js").text
    mfa_verify_page = client.get("/ui/mfa/verify").text
    assert 'data-code-type="totp"' in mfa_verify_page
    assert 'data-code-type="recovery"' in mfa_verify_page
    assert "Gửi lại mã" not in mfa_verify_page


def test_organization_sidebar_uses_real_paths_and_each_route_renders_one_panel(client):
    members = client.get("/ui/organization")
    policy = client.get("/ui/organization/policy")
    break_glass = client.get("/ui/organization/break-glass")
    audit = client.get("/ui/organization/audit")
    for response in (members, policy, break_glass, audit):
        assert response.status_code == 200
        assert 'href="/ui/organization/policy"' in response.text
        assert 'href="/ui/organization/break-glass"' in response.text
        assert 'href="/ui/organization/audit"' in response.text
        assert "/ui/organization#" not in response.text
        assert 'src="/static/organization.js?v=' in response.text

    assert 'data-section="organization"' in members.text
    assert 'data-organization-panel="organization"' in members.text
    assert 'id="invitation-dialog"' in members.text
    assert 'data-organization-panel="policy"' not in members.text
    assert 'data-organization-panel="break-glass"' not in members.text
    assert 'data-organization-panel="audit"' not in members.text

    assert 'data-section="policy"' in policy.text
    assert 'data-organization-panel="policy"' in policy.text
    assert 'data-organization-panel="organization"' not in policy.text
    assert 'id="invitation-dialog"' not in policy.text

    assert 'data-section="break-glass"' in break_glass.text
    assert 'data-organization-panel="break-glass"' in break_glass.text
    assert 'id="grant-decision-dialog"' in break_glass.text
    assert 'data-organization-panel="audit"' not in break_glass.text

    assert 'data-section="audit"' in audit.text
    assert 'data-organization-panel="audit"' in audit.text
    assert 'id="grant-decision-dialog"' not in audit.text

    script = client.get("/static/organization.js").text
    assert 'if (section === "organization")' in script
    assert 'else if (section === "policy")' in script
    assert 'else if (section === "break-glass")' in script
    assert 'else if (section === "audit")' in script
    assert "loadMembers(), loadOrganizationOverview(), loadPolicy()" not in script
    assert "function redirectLegacyOrganizationHash()" in script


def test_account_and_organization_settings_shells_expose_expected_fields(client):
    account = client.get("/ui/settings")
    organization = client.get("/ui/organization/settings")
    assert account.status_code == 200
    assert 'id="account-profile-form"' in account.text
    assert 'id="account-password-form"' in account.text
    assert 'id="settings-avatar-url"' in account.text
    assert 'id="account-profile-form" class="settings-form" aria-busy="true"' in account.text
    assert organization.status_code == 200
    assert 'id="organization-profile-form"' in organization.text
    assert 'id="settings-organization-address"' in organization.text
    assert 'id="settings-organization-website"' in organization.text
    assert 'id="organization-profile-form" class="settings-form" aria-busy="true"' in organization.text

    api_script = client.get("/static/api.js").text
    account_script = client.get("/static/account-settings.js").text
    organization_script = client.get("/static/organization-settings.js").text
    assert "function apiErrorMessage(payload, fallback)" in api_script
    assert 'accountAvatar.classList.add("has-image")' in api_script
    assert 'displayNameInput.addEventListener("input", refreshPreview)' in account_script
    assert 'nameInput.addEventListener("input", refreshPreview)' in organization_script
    assert "preview.contains(image)" in account_script
    assert "preview.contains(image)" in organization_script


def test_current_user_exposes_server_resolved_capabilities(client):
    registered = client.post(
        "/auth/register",
        json={
            "organization_name": "Capability UI Org",
            "admin_email": "capability-ui@test.local",
            "admin_password": "matkhau123",
        },
    )
    token = registered.json()["access_token"]
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["effective_role"] == "org_admin"
    assert body["active_org_id"] == body["org_id"]
    assert body["is_system_admin"] is False
    assert "org.members.manage" in body["capabilities"]
    assert not any(capability.startswith("exam.") for capability in body["capabilities"])
    assert "system.organizations.read" not in body["capabilities"]


def test_request_id_is_returned_on_admin_pages(client):
    response = client.get("/ui/system")
    assert response.headers["x-request-id"]
