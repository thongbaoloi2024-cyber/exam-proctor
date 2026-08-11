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
        "/ui/exams/exam-id/detail": "/static/dashboard.js",
        "/ui/exams/exam-id/detail?tab=manage": "/static/exam_manage.js",
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

    stylesheet = client.get("/static/style.css").text
    assert ".auth-page .page" in stylesheet
    assert "min-height: 100dvh" in stylesheet
    assert "@media (min-width: 781px) and (max-height: 820px)" in stylesheet


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


def test_admin_pages_use_clear_vietnamese_security_terms(client):
    system_overview = client.get("/ui/system")
    system_security = client.get("/ui/system/security")
    system_evidence = client.get("/ui/system/evidence")
    system_activity = client.get("/ui/system/audit")
    organization_overview = client.get("/ui/organization/overview")
    organization_access = client.get("/ui/organization/break-glass")
    organization_activity = client.get("/ui/organization/audit")

    assert "Tình trạng vận hành" in system_overview.text
    assert "Tạo yêu cầu quyền truy cập ngoại lệ" in system_security.text
    assert "Sự kiện bảo mật" in system_security.text
    assert "Dữ liệu được cấp quyền" in system_evidence.text
    assert "Nhật ký hoạt động" in system_activity.text
    assert "Tài khoản đã bật MFA" in organization_overview.text
    assert "hạn mức phiên đồng thời" in organization_overview.text
    assert "Yêu cầu quyền truy cập ngoại lệ" in organization_access.text
    assert "Nhật ký hoạt động" in organization_activity.text
    assert "Độ phủ MFA" not in organization_overview.text
    assert "Security events" not in system_security.text


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


def test_exam_table_supports_sorting_and_pagination(client):
    page = client.get("/ui/exams")
    assert page.status_code == 200
    assert "Thời gian tạo" in page.text
    assert 'data-exam-sort="status"' in page.text
    assert 'aria-sort="ascending"' in page.text
    assert 'id="exam-pagination"' in page.text

    script = client.get("/static/exams.js").text
    assert "const EXAMS_PAGE_SIZE = 15" in script
    assert "const EXAM_STATUS_ORDER" in script
    assert "function sortedExams()" in script
    assert "function renderExamPagination" in script
    assert 'copyButton.className = "exam-code-copy"' in script
    assert 'copyButton.textContent = "Chép"' not in script
    assert 'nameContent.className = "exam-name-cell"' in script
    assert 'actionsCell.appendChild(actions)' in script

    stylesheet = client.get("/static/style.css").text
    assert ".exams-container { max-width: 1400px; }" in stylesheet
    assert ".table-sort-button" in stylesheet
    assert ".exam-code-copy" in stylesheet


def test_data_workspaces_use_wide_responsive_containers(client):
    workspace_pages = (
        client.get("/ui/exams/exam-id/detail"),
        client.get("/ui/exams/exam-id/detail?tab=manage"),
        client.get("/ui/exams/exam-id/sessions/session-id"),
        client.get("/ui/organization"),
        client.get("/ui/organization/audit"),
    )
    for page in workspace_pages:
        assert page.status_code == 200
        assert 'class="container workspace-container"' in page.text

    dashboard = workspace_pages[0].text
    assert 'id="sessions-table" class="data-table workspace-table workspace-table-wide"' in dashboard
    assert 'id="incidents-table" class="data-table workspace-table"' in dashboard

    session_detail = workspace_pages[2].text
    assert session_detail.count('class="data-table workspace-table"') == 3

    stylesheet = client.get("/static/style.css").text
    assert ".system-container, .workspace-container { max-width: 1400px;" in stylesheet
    assert ".workspace-table-wide { min-width: 1080px; }" in stylesheet
    assert '.organization-panel[data-organization-panel="policy"]' in stylesheet

    organizations_script = client.get("/static/system-organizations.js").text
    security_script = client.get("/static/system-security.js").text
    assert "pageSize: 15" in organizations_script
    assert "pageSize: 15" in security_script


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
    assert '<th>Người dùng</th>' in audit.text
    assert '<th>Request ID</th>' not in audit.text
    assert 'id="organization-audit-pagination"' in audit.text

    script = client.get("/static/organization.js").text
    assert 'if (section === "organization")' in script
    assert 'else if (section === "policy")' in script
    assert 'else if (section === "break-glass")' in script
    assert 'else if (section === "audit")' in script
    assert "loadMembers(), loadOrganizationOverview(), loadPolicy()" not in script
    assert "function redirectLegacyOrganizationHash()" in script
    assert 'API.request(`/organizations/current/audit/page?${params}`)' in script


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


def test_shared_pages_include_and_persist_accessible_theme_toggle(client):
    for path in ("/ui/login", "/ui/exams", "/ui/system"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'id="theme-toggle"' in response.text
        assert 'class="theme-icon theme-icon-sun"' in response.text
        assert 'class="theme-icon theme-icon-moon"' in response.text
        assert 'aria-label="Chuyển sang giao diện sáng"' in response.text
        assert 'aria-pressed="false"' in response.text
        assert response.text.index("/static/theme.js") < response.text.index("/static/style.css")

    script_response = client.get("/static/theme.js")
    assert script_response.status_code == 200
    script = script_response.text
    assert 'const STORAGE_KEY = "giam-thi-so-theme"' in script
    assert 'const DEFAULT_THEME = "dark"' in script
    assert "localStorage.getItem(STORAGE_KEY)" in script
    assert "localStorage.setItem(STORAGE_KEY, nextTheme)" in script
    assert "document.documentElement.dataset.theme = nextTheme" in script
    assert 'currentTheme === "dark" ? "light" : "dark"' in script
    assert 'toggle.setAttribute("aria-pressed", String(lightThemeActive))' in script

    stylesheet_response = client.get("/static/style.css")
    assert stylesheet_response.status_code == 200
    stylesheet = stylesheet_response.text
    assert ':root[data-theme="light"]' in stylesheet
    assert "color-scheme: dark" in stylesheet
    assert "color-scheme: light" in stylesheet
    assert ".theme-toggle" in stylesheet
    assert "position: fixed" in stylesheet
    assert ".theme-icon-sun" in stylesheet
    assert ".theme-icon-moon" in stylesheet
