function orgCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value == null ? "–" : String(value);
  row.appendChild(cell);
  return cell;
}

function orgSelect(options, selectedValue) {
  const select = document.createElement("select");
  select.replaceChildren(...options.map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  }));
  select.value = selectedValue;
  return select;
}

const ORGANIZATION_SECTIONS = new Set(["organization", "policy", "break-glass", "audit"]);

function getOrganizationSection() {
  const requestedSection = window.location.hash.slice(1);
  return ORGANIZATION_SECTIONS.has(requestedSection) ? requestedSection : "organization";
}

function updateOrganizationSection() {
  const currentSection = getOrganizationSection();
  document.querySelectorAll("[data-organization-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.organizationPanel !== currentSection);
  });
  document.querySelectorAll("#organization-nav-section .nav-item").forEach((item) => {
    const section = item.dataset.organizationNav || "organization";
    const isActive = section === currentSection;
    item.classList.toggle("active", isActive);
    if (isActive) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
}

function bindOrganizationNavigation() {
  document.querySelectorAll("#organization-nav-section [data-organization-nav]").forEach((item) => {
    item.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const section = item.dataset.organizationNav;
      const nextHash = section === "organization" ? "" : `#${section}`;
      const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (nextUrl !== currentUrl) window.history.pushState(null, "", nextUrl);
      updateOrganizationSection();
    });
  });
}

function bindInvitationDialog() {
  const dialog = document.getElementById("invitation-dialog");
  const result = document.getElementById("invitation-result");
  document.getElementById("open-invitation-dialog").addEventListener("click", () => {
    result.classList.add("hidden");
    result.textContent = "";
    dialog.showModal();
    document.getElementById("invitation-email").focus();
  });
  dialog.querySelectorAll(".dialog-close").forEach((button) => {
    button.addEventListener("click", () => dialog.close());
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
}

async function loadOrganization() {
  const response = await API.request("/organizations/current");
  if (!response.ok) throw new Error("Không tải được tổ chức.");
  const organization = await response.json();
  const title = document.getElementById("sidebar-brand-title");
  const meta = document.getElementById("sidebar-brand-context");
  const metaText = `${organization.status} · retention ${organization.retention_days} ngày`;
  if (title) {
    title.textContent = organization.name;
    title.title = organization.name;
  }
  if (meta) {
    meta.textContent = metaText;
    meta.title = metaText;
  }
}

async function updateMember(userId, role, status) {
  const response = await API.request(`/organizations/current/members/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify({ role, status }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    showToast(body.detail || "Không cập nhật được thành viên.", "error");
    return;
  }
  showToast("Đã cập nhật thành viên và thu hồi phiên cũ.", "success");
  await Promise.all([loadMembers(), loadOrganizationAudit()]);
}

async function loadMembers() {
  const response = await API.request("/organizations/current/members");
  if (!response.ok) throw new Error("Không tải được thành viên.");
  const members = await response.json();
  const rows = members.map((member) => {
    const row = document.createElement("tr");
    orgCell(row, member.email);
    const roleCell = document.createElement("td");
    const role = orgSelect(
      [["exam_manager", "Exam Manager"], ["org_admin", "Organization Admin"]],
      member.role,
    );
    roleCell.appendChild(role);
    row.appendChild(roleCell);
    const statusCell = document.createElement("td");
    const memberStatus = orgSelect(
      [["active", "Active"], ["suspended", "Suspended"], ["revoked", "Revoked"]],
      member.membership_status,
    );
    statusCell.appendChild(memberStatus);
    row.appendChild(statusCell);
    const actionCell = document.createElement("td");
    const save = document.createElement("button");
    save.textContent = "Lưu";
    save.addEventListener("click", () => updateMember(member.user_id, role.value, memberStatus.value));
    actionCell.appendChild(save);
    row.appendChild(actionCell);
    return row;
  });
  document.querySelector("#members-table tbody").replaceChildren(...rows);
}

async function loadPolicy() {
  const response = await API.request("/organizations/current/policy");
  if (!response.ok) return;
  const policy = await response.json();
  document.getElementById("policy-extension-version").value = policy.min_extension_version;
  document.getElementById("policy-retention").value = policy.retention_days;
  document.getElementById("policy-focus").value = policy.max_focus_loss_seconds;
  document.getElementById("policy-require-extension").checked = policy.require_extension;
  document.getElementById("policy-require-camera").checked = policy.require_camera;
  document.getElementById("policy-require-fullscreen").checked = policy.require_fullscreen;
}

async function grantAction(id, action) {
  const response = await API.request(`/organizations/current/access-grants/${encodeURIComponent(id)}/${action}`, { method: "POST" });
  if (!response.ok) {
    showToast("Không cập nhật được yêu cầu break-glass.", "error");
    return;
  }
  await Promise.all([loadAccessGrants(), loadOrganizationAudit()]);
}

async function loadAccessGrants() {
  const response = await API.request("/organizations/current/access-grants");
  if (!response.ok) return;
  const grants = await response.json();
  const rows = grants.map((grant) => {
    const row = document.createElement("tr");
    orgCell(row, grant.reason);
    orgCell(row, grant.status);
    orgCell(row, new Date(grant.expires_at).toLocaleString("vi-VN"));
    const actions = document.createElement("td");
    if (grant.status === "pending") {
      const approve = document.createElement("button");
      approve.textContent = "Duyệt";
      approve.addEventListener("click", () => grantAction(grant.id, "approve"));
      actions.appendChild(approve);
    } else if (grant.status === "active") {
      const revoke = document.createElement("button");
      revoke.textContent = "Thu hồi";
      revoke.addEventListener("click", () => grantAction(grant.id, "revoke"));
      actions.appendChild(revoke);
    }
    row.appendChild(actions);
    return row;
  });
  document.querySelector("#access-grants-table tbody").replaceChildren(...rows);
}

async function loadOrganizationAudit() {
  const response = await API.request("/organizations/current/audit?limit=50");
  if (!response.ok) return;
  const entries = await response.json();
  const rows = entries.map((entry) => {
    const row = document.createElement("tr");
    orgCell(row, new Date(entry.created_at).toLocaleString("vi-VN"));
    orgCell(row, entry.action);
    orgCell(row, entry.resource_type);
    orgCell(row, entry.outcome);
    return row;
  });
  document.querySelector("#organization-audit-table tbody").replaceChildren(...rows);
}

document.getElementById("invitation-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await API.request("/organizations/current/invitations", {
    method: "POST",
    body: JSON.stringify({
      email: document.getElementById("invitation-email").value,
      role: document.getElementById("invitation-role").value,
    }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    showToast(body.detail || "Không tạo được lời mời.", "error");
    return;
  }
  const result = document.getElementById("invitation-result");
  result.classList.remove("hidden");
  result.textContent = `Token lời mời (chỉ hiển thị lần này): ${body.invitation_token}`;
  document.getElementById("invitation-email").value = "";
  await loadOrganizationAudit();
});

document.getElementById("policy-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await API.request("/organizations/current/policy", {
    method: "PUT",
    body: JSON.stringify({
      default_candidate_auth_mode: "manual",
      min_extension_version: document.getElementById("policy-extension-version").value,
      require_extension: document.getElementById("policy-require-extension").checked,
      require_fullscreen: document.getElementById("policy-require-fullscreen").checked,
      require_camera: document.getElementById("policy-require-camera").checked,
      require_microphone: false,
      require_screen_share: false,
      block_clipboard: true,
      max_focus_loss_seconds: Number(document.getElementById("policy-focus").value),
      retention_days: Number(document.getElementById("policy-retention").value),
    }),
  });
  showToast(response.ok ? "Đã lưu chính sách." : "Không lưu được chính sách.", response.ok ? "success" : "error");
  if (response.ok) await loadOrganizationAudit();
});

async function initializeOrganization() {
  bindOrganizationNavigation();
  updateOrganizationSection();
  const user = await API.requireAuth();
  if (!user) return;
  if (!API.hasCapability("org.members.read")) {
    window.location.replace("/ui/exams");
    return;
  }
  updateOrganizationSection();
  bindInvitationDialog();
  await Promise.all([loadOrganization(), loadMembers(), loadPolicy(), loadAccessGrants(), loadOrganizationAudit()]);
}

window.addEventListener("hashchange", updateOrganizationSection);
window.addEventListener("popstate", updateOrganizationSection);
initializeOrganization().catch((error) => showToast(error.message, "error"));
