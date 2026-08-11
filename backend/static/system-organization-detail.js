const organizationDetailState = {
  id: document.getElementById("system-organization-detail").dataset.organizationId,
  organization: null,
};

function renderOrganizationAdmins(administrators) {
  const list = document.getElementById("organization-admin-list");
  if (!administrators.length) {
    list.replaceChildren(SystemUI.empty("Chưa có Organization Admin."));
    return;
  }
  list.replaceChildren(...administrators.map((administrator) => {
    const row = document.createElement("div");
    row.className = "person-row";
    const avatar = document.createElement("span");
    avatar.className = "person-avatar";
    avatar.textContent = administrator.email.slice(0, 2).toUpperCase();
    const info = document.createElement("span");
    const email = document.createElement("strong");
    email.textContent = administrator.email;
    const role = document.createElement("small");
    role.textContent = "Organization Admin";
    info.append(email, role);
    row.append(avatar, info, SystemUI.badge(administrator.status));
    return row;
  }));
}

function renderOrganizationAudit(entries) {
  const list = document.getElementById("organization-audit-list");
  if (!entries.length) {
    list.replaceChildren(SystemUI.empty("Chưa có hoạt động quản trị."));
    return;
  }
  list.replaceChildren(...entries.map((entry) => {
    const row = document.createElement("div");
    row.className = "timeline-item";
    const marker = document.createElement("span");
    marker.className = `timeline-marker ${entry.outcome === "success" ? "success" : "warning"}`;
    const content = document.createElement("div");
    const action = document.createElement("strong");
    action.textContent = entry.action;
    const meta = document.createElement("small");
    meta.textContent = `${entry.resource_type}${entry.resource_id ? ` · ${entry.resource_id}` : ""}`;
    content.append(action, meta);
    const time = document.createElement("time");
    time.dateTime = entry.created_at;
    time.textContent = SystemUI.formatDate(entry.created_at, true);
    row.append(marker, content, time);
    return row;
  }));
}

function renderOrganizationDetail(data) {
  const organization = data.organization;
  organizationDetailState.organization = organization;
  SystemUI.text("organization-name", organization.name);
  SystemUI.text("organization-meta", `${organization.slug || organization.id} · Tạo ngày ${SystemUI.formatDate(organization.created_at)}`);
  const statusBadge = document.getElementById("organization-status-badge");
  statusBadge.className = `status-badge status-${organization.status}`;
  statusBadge.textContent = SystemUI.statusLabel(organization.status);
  SystemUI.text("detail-users", SystemUI.formatNumber(organization.user_count));
  SystemUI.text("detail-admins-caption", `${SystemUI.formatNumber(organization.org_admin_count)} quản trị viên`);
  SystemUI.text("detail-exams", SystemUI.formatNumber(organization.exam_count));
  SystemUI.text("detail-sessions", SystemUI.formatNumber(organization.active_session_count));
  SystemUI.text("detail-retention", `${SystemUI.formatNumber(organization.retention_days)} ngày`);
  SystemUI.text("detail-slug", organization.slug || "Chưa thiết lập");
  SystemUI.text("detail-quota", organization.quota_concurrent_sessions ? SystemUI.formatNumber(organization.quota_concurrent_sessions) : "Không giới hạn");
  SystemUI.text("detail-created", SystemUI.formatDate(organization.created_at, true));
  SystemUI.text("detail-updated", SystemUI.formatDate(organization.updated_at, true));
  SystemUI.text("quota-current", SystemUI.formatNumber(organization.active_session_count));
  SystemUI.text("quota-limit", organization.quota_concurrent_sessions ? `/ ${SystemUI.formatNumber(organization.quota_concurrent_sessions)}` : "/ ∞");
  const quotaPercent = organization.quota_concurrent_sessions
    ? Math.min(100, (organization.active_session_count / organization.quota_concurrent_sessions) * 100)
    : 0;
  const progress = document.getElementById("quota-progress");
  progress.style.width = `${quotaPercent}%`;
  progress.parentElement.setAttribute("aria-valuenow", String(Math.round(quotaPercent)));
  SystemUI.text(
    "quota-caption",
    organization.quota_concurrent_sessions
      ? `${Math.round(quotaPercent)}% hạn mức đang được sử dụng`
      : "Tổ chức hiện không bị giới hạn phiên đồng thời",
  );
  const statusButton = document.getElementById("toggle-organization-status");
  statusButton.textContent = organization.status === "active" ? "Tạm khóa" : "Mở khóa";
  statusButton.classList.toggle("danger-outline", organization.status === "active");
  statusButton.disabled = false;
  document.getElementById("edit-organization").disabled = false;
  SystemUI.renderLineChart("organization-session-chart", data.session_trend);
  renderOrganizationAdmins(data.administrators);
  renderOrganizationAudit(data.recent_audit);
}

async function loadOrganizationDetail() {
  const data = await SystemUI.fetchJson(
    `/system/organizations/${encodeURIComponent(organizationDetailState.id)}?days=30`,
  );
  renderOrganizationDetail(data);
}

async function saveOrganizationSettings(event) {
  event.preventDefault();
  const submit = event.submitter;
  const quota = document.getElementById("edit-quota").value;
  SystemUI.setBusy(submit, true);
  try {
    await SystemUI.fetchJson(`/system/organizations/${encodeURIComponent(organizationDetailState.id)}`, {
      method: "PATCH",
      body: JSON.stringify({
        retention_days: Number(document.getElementById("edit-retention").value),
        quota_concurrent_sessions: quota ? Number(quota) : null,
        reason: document.getElementById("edit-reason").value,
      }),
    });
    document.getElementById("edit-organization-dialog").close();
    showToast("Đã lưu cấu hình tổ chức.", "success");
    await loadOrganizationDetail();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    SystemUI.setBusy(submit, false);
  }
}

async function updateDetailStatus(event) {
  event.preventDefault();
  const submit = event.submitter;
  const nextStatus = organizationDetailState.organization.status === "active" ? "suspended" : "active";
  SystemUI.setBusy(submit, true);
  try {
    await SystemUI.fetchJson(`/system/organizations/${encodeURIComponent(organizationDetailState.id)}`, {
      method: "PATCH",
      body: JSON.stringify({
        status: nextStatus,
        reason: document.getElementById("detail-status-reason").value,
      }),
    });
    document.getElementById("detail-status-dialog").close();
    showToast("Đã cập nhật trạng thái tổ chức.", "success");
    await loadOrganizationDetail();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    SystemUI.setBusy(submit, false);
  }
}

async function submitBreakGlass(event) {
  event.preventDefault();
  const submit = event.submitter;
  SystemUI.setBusy(submit, true, "Đang gửi...");
  try {
    await SystemUI.fetchJson("/system/access-grants", {
      method: "POST",
      body: JSON.stringify({
        org_id: organizationDetailState.id,
        reason: document.getElementById("break-glass-reason").value,
        scope: "evidence.read",
        requested_duration_minutes: Number(document.getElementById("break-glass-duration").value),
      }),
    });
    document.getElementById("break-glass-dialog").close();
    event.target.reset();
    showToast("Đã gửi yêu cầu; Organization Admin cần phê duyệt.", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    SystemUI.setBusy(submit, false);
  }
}

async function submitAdminInvitation(event) {
  event.preventDefault();
  const submit = event.submitter;
  SystemUI.setBusy(submit, true, "Đang tạo...");
  try {
    const data = await SystemUI.fetchJson(`/system/organizations/${encodeURIComponent(organizationDetailState.id)}/admin-invitations`, {
      method: "POST",
      body: JSON.stringify({ email: document.getElementById("invite-admin-email").value, expires_in_hours: Number(document.getElementById("invite-admin-hours").value) }),
    });
    const result = document.getElementById("invite-admin-result");
    result.classList.remove("hidden");
    result.textContent = `Token lời mời: ${data.invitation_token}`;
    showToast("Đã tạo lời mời Organization Admin.", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    SystemUI.setBusy(submit, false);
  }
}

async function initializeOrganizationDetail() {
  const user = await SystemUI.initialize();
  if (!user) return;
  document.getElementById("edit-organization").addEventListener("click", () => {
    const organization = organizationDetailState.organization;
    document.getElementById("edit-retention").value = organization.retention_days;
    document.getElementById("edit-quota").value = organization.quota_concurrent_sessions || "";
    document.getElementById("edit-reason").value = "";
    document.getElementById("edit-organization-dialog").showModal();
  });
  document.getElementById("toggle-organization-status").addEventListener("click", () => {
    const suspending = organizationDetailState.organization.status === "active";
    SystemUI.text("detail-status-title", suspending ? "Tạm khóa tổ chức" : "Mở khóa tổ chức");
    SystemUI.text(
      "detail-status-description",
      suspending ? "Mọi phiên đăng nhập của thành viên sẽ bị thu hồi." : "Tổ chức sẽ được phép hoạt động trở lại.",
    );
    document.getElementById("detail-status-reason").value = "";
    document.getElementById("detail-status-dialog").showModal();
  });
  document.getElementById("request-break-glass").addEventListener("click", () => {
    document.getElementById("break-glass-dialog").showModal();
  });
  document.getElementById("invite-organization-admin").addEventListener("click", () => {
    document.getElementById("invite-admin-result").classList.add("hidden");
    document.getElementById("invite-admin-dialog").showModal();
  });
  document.getElementById("edit-organization-form").addEventListener("submit", saveOrganizationSettings);
  document.getElementById("detail-status-form").addEventListener("submit", updateDetailStatus);
  document.getElementById("break-glass-form").addEventListener("submit", submitBreakGlass);
  document.getElementById("invite-admin-form").addEventListener("submit", submitAdminInvitation);
  try {
    await loadOrganizationDetail();
  } catch (error) {
    showToast(error.message, "error");
    SystemUI.text("organization-name", "Không tải được tổ chức");
  }
}

initializeOrganizationDetail();
