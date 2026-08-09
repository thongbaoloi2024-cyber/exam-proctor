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
        "/ui/organization": "/static/organization.js",
        "/ui/mfa": "/static/mfa.js",
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
    assert '? "/ui/organization"' in login_script


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

    api_script = client.get("/static/api.js").text
    assert 'document.body.classList.toggle("has-system-sidebar", isSystemAdmin)' in api_script
    assert 'isOrganizationAdmin ? "/ui/organization" : "/ui/exams"' in api_script


def test_tenant_sidebars_are_role_aware_and_capability_scoped(client):
    response = client.get("/ui/exams")
    assert response.status_code == 200
    assert 'id="tenant-nav-group"' in response.text
    assert 'id="exam-nav-section"' in response.text
    assert 'id="organization-nav-section"' in response.text
    assert 'id="organization-platform-badge"' in response.text
    assert 'id="exam-platform-badge"' in response.text
    assert "Vận hành kỳ thi" in response.text
    assert "Quản trị tổ chức" in response.text

    api_script = client.get("/static/api.js").text
    assert 'document.body.classList.toggle("has-role-sidebar", isAuthenticated)' in api_script
    assert 'document.body.classList.toggle("has-organization-sidebar", isOrganizationAdmin)' in api_script
    assert 'document.body.classList.toggle("has-exam-manager-sidebar", isExamManager)' in api_script
    assert "const canUseExams = !isOrganizationAdmin" in api_script
    assert 'this.hasCapability("org.members.read")' in api_script
    assert 'this.hasCapability("exam.read") || this.hasCapability("exam.create")' in api_script

    stylesheet = client.get("/static/style.css").text
    assert ".has-organization-sidebar" in stylesheet
    assert ".has-exam-manager-sidebar" in stylesheet
    assert "--sidebar-accent-rgb" in stylesheet
    exams_script = client.get("/static/exams.js").text
    assert 'currentUser.effective_role === "org_admin"' in exams_script
    assert 'window.location.replace("/ui/organization")' in exams_script
    mfa_page = client.get("/ui/mfa").text
    assert 'id="mfa-qr"' in mfa_page
    assert "qr_code_data_url" in client.get("/static/mfa.js").text


def test_organization_sidebar_sections_and_invitation_dialog(client):
    response = client.get("/ui/organization")
    assert response.status_code == 200
    assert 'id="nav-organization" data-organization-nav="organization"' in response.text
    assert 'id="nav-organization-policy" data-organization-nav="policy"' in response.text
    assert 'id="nav-organization-break-glass" data-organization-nav="break-glass"' in response.text
    assert 'id="nav-organization-audit" data-organization-nav="audit"' in response.text
    assert 'data-organization-panel="organization"' in response.text
    assert 'data-organization-panel="policy"' in response.text
    assert 'data-organization-panel="break-glass"' in response.text
    assert 'data-organization-panel="audit"' in response.text
    assert 'id="open-invitation-dialog"' in response.text
    assert 'id="invitation-dialog"' in response.text
    assert 'src="/static/organization.js?v=' in response.text

    script = client.get("/static/organization.js").text
    assert "function bindOrganizationNavigation()" in script
    assert "window.history.pushState" in script
    assert 'window.addEventListener("popstate", updateOrganizationSection)' in script


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
