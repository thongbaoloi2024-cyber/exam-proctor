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

let selectedGrantDecision = null;
const LEGACY_ORGANIZATION_HASH_PATHS = {
  policy: "/ui/organization/policy",
  "break-glass": "/ui/organization/break-glass",
  audit: "/ui/organization/audit",
};

function redirectLegacyOrganizationHash() {
  if (window.location.pathname !== "/ui/organization") return false;
  const legacyPath = LEGACY_ORGANIZATION_HASH_PATHS[window.location.hash.slice(1)];
  if (!legacyPath) return false;
  window.location.replace(`${legacyPath}${window.location.search}`);
  return true;
}

function getOrganizationSection() {
  return document.getElementById("organization-page")?.dataset.section || "organization";
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

function bindGrantDecisionDialog() {
  const dialog = document.getElementById("grant-decision-dialog");
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
  document.getElementById("organization-name").value = organization.name;
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

async function loadOrganizationOverview() {
  const response = await API.request("/organizations/current/overview");
  if (!response.ok) return;
  const data = await response.json();
  const tiles = [
    ["Thành viên active", `${data.members_active}/${data.members_total}`],
    ["Đã bật MFA", `${data.members_with_mfa}/${data.members_total}`],
    ["Lời mời chờ", data.pending_invitations],
    ["Kỳ thi", data.exams_total],
    ["Phiên đồng thời", `${data.sessions_active}/${data.concurrent_session_quota ?? "∞"}`],
    ["Retention", `${data.retention_days} ngày`],
  ];
  document.getElementById("organization-kpis").replaceChildren(...tiles.map(([labelText, valueText]) => {
    const tile = document.createElement("div"); tile.className = "kpi-tile";
    const value = document.createElement("div"); value.className = "kpi-value"; value.textContent = valueText;
    const label = document.createElement("div"); label.className = "kpi-label"; label.textContent = labelText;
    tile.append(value, label); return tile;
  }));
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
  await Promise.all([loadMembers(), loadOrganizationOverview()]);
}

async function loadMembers() {
  const response = await API.request("/organizations/current/members");
  if (!response.ok) throw new Error("Không tải được thành viên.");
  const members = await response.json();
  const rows = members.map((member) => {
    const row = document.createElement("tr");
    const emailCell = orgCell(row, member.email);
    if (member.mfa_enabled) { const badge = document.createElement("span"); badge.className = "badge badge-low member-mfa-badge"; badge.textContent = "MFA"; emailCell.appendChild(badge); }
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

async function loadInvitations() {
  const response = await API.request("/organizations/current/invitations");
  if (!response.ok) return;
  const invitations = await response.json();
  const tbody = document.querySelector("#invitations-table tbody");
  if (!invitations.length) {
    const row = document.createElement("tr"); const cell = orgCell(row, "Không có lời mời."); cell.colSpan = 6; tbody.replaceChildren(row); return;
  }
  tbody.replaceChildren(...invitations.map((invitation) => {
    const row = document.createElement("tr");
    orgCell(row, invitation.email); orgCell(row, invitation.role); orgCell(row, invitation.status);
    orgCell(row, new Date(invitation.created_at).toLocaleString("vi-VN")); orgCell(row, new Date(invitation.expires_at).toLocaleString("vi-VN"));
    const action = document.createElement("td");
    if (invitation.status === "pending") { const revoke = document.createElement("button"); revoke.type = "button"; revoke.className = "secondary-button"; revoke.textContent = "Thu hồi"; revoke.addEventListener("click", () => revokeInvitation(invitation.id)); action.appendChild(revoke); }
    row.appendChild(action); return row;
  }));
}

async function revokeInvitation(id) {
  if (!confirm("Thu hồi lời mời này?")) return;
  const response = await API.request(`/organizations/current/invitations/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!response.ok) return showToast("Không thu hồi được lời mời.", "error");
  showToast("Đã thu hồi lời mời.", "success"); await Promise.all([loadInvitations(), loadOrganizationOverview()]);
}

async function loadPolicy() {
  const response = await API.request("/organizations/current/policy");
  if (!response.ok) return;
  const policy = await response.json();
  document.getElementById("policy-auth-mode").value = policy.default_candidate_auth_mode;
  document.getElementById("policy-extension-version").value = policy.min_extension_version;
  document.getElementById("policy-retention").value = policy.retention_days;
  document.getElementById("policy-focus").value = policy.max_focus_loss_seconds;
  document.getElementById("policy-require-extension").checked = policy.require_extension;
  document.getElementById("policy-require-camera").checked = policy.require_camera;
  document.getElementById("policy-require-fullscreen").checked = policy.require_fullscreen;
  document.getElementById("policy-require-microphone").checked = policy.require_microphone;
  document.getElementById("policy-require-screen-share").checked = policy.require_screen_share;
  document.getElementById("policy-block-clipboard").checked = policy.block_clipboard;
  syncOrganizationPolicyConstraints();
}

function syncOrganizationPolicyConstraints() {
  const google = document.getElementById("policy-auth-mode").value === "google";
  const requireExtension = document.getElementById("policy-require-extension");
  if (google) requireExtension.checked = true;
  requireExtension.disabled = google;
}

function openGrantDecision(grant, action) {
  selectedGrantDecision = { grant, action };
  document.getElementById("grant-decision-title").textContent = action === "approve"
    ? "Phê duyệt break-glass"
    : "Thu hồi break-glass";
  document.getElementById("grant-decision-requester").textContent = grant.requester_email;
  document.getElementById("grant-decision-scope").textContent = `${grant.scope} · ${grant.read_only ? "chỉ đọc" : "có thể chỉnh sửa"}`;
  document.getElementById("grant-decision-expiry").textContent = new Date(grant.expires_at).toLocaleString("vi-VN");
  document.getElementById("grant-decision-request-reason").textContent = grant.reason;
  document.getElementById("grant-decision-reason").value = "";
  document.getElementById("grant-verification-code").value = "";
  document.getElementById("grant-decision-submit").textContent = action === "approve" ? "Phê duyệt" : "Thu hồi";
  document.getElementById("grant-decision-dialog").showModal();
}

async function grantAction(event) {
  event.preventDefault();
  if (!selectedGrantDecision) return;
  const { grant, action } = selectedGrantDecision;
  const response = await API.request(`/organizations/current/access-grants/${encodeURIComponent(grant.id)}/${action}`, {
    method: "POST",
    body: JSON.stringify({
      decision_reason: document.getElementById("grant-decision-reason").value,
      verification_code: document.getElementById("grant-verification-code").value,
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    showToast(body.detail || "Không cập nhật được yêu cầu break-glass.", "error");
    return;
  }
  document.getElementById("grant-decision-dialog").close();
  showToast(action === "approve" ? "Đã phê duyệt quyền chỉ đọc." : "Đã thu hồi quyền break-glass.", "success");
  await loadAccessGrants();
}

async function loadAccessGrants() {
  const response = await API.request("/organizations/current/access-grants");
  if (!response.ok) return;
  const grants = await response.json();
  const rows = grants.map((grant) => {
    const row = document.createElement("tr");
    orgCell(row, grant.requester_email);
    orgCell(row, grant.reason);
    orgCell(row, `${grant.scope} · ${grant.read_only ? "Chỉ đọc" : "Có ghi"}`);
    orgCell(row, new Date(grant.created_at).toLocaleString("vi-VN"));
    orgCell(row, grant.effective_status);
    orgCell(row, new Date(grant.expires_at).toLocaleString("vi-VN"));
    const actions = document.createElement("td");
    if (grant.effective_status === "pending") {
      const approve = document.createElement("button");
      approve.textContent = "Duyệt";
      approve.addEventListener("click", () => openGrantDecision(grant, "approve"));
      actions.appendChild(approve);
    } else if (grant.effective_status === "active") {
      const revoke = document.createElement("button");
      revoke.textContent = "Thu hồi";
      revoke.addEventListener("click", () => openGrantDecision(grant, "revoke"));
      actions.appendChild(revoke);
    }
    row.appendChild(actions);
    return row;
  });
  document.querySelector("#access-grants-table tbody").replaceChildren(...rows);
}

async function loadOrganizationAudit() {
  const params = new URLSearchParams({ limit: "100" });
  const search = document.getElementById("audit-search").value.trim();
  const outcome = document.getElementById("audit-outcome").value;
  if (search) params.set("search", search);
  if (outcome) params.set("outcome", outcome);
  const response = await API.request(`/organizations/current/audit?${params}`);
  if (!response.ok) return;
  const entries = await response.json();
  const rows = entries.map((entry) => {
    const row = document.createElement("tr");
    orgCell(row, new Date(entry.created_at).toLocaleString("vi-VN"));
    orgCell(row, entry.actor_user_id || "Hệ thống");
    orgCell(row, entry.action);
    orgCell(row, `${entry.resource_type}${entry.resource_id ? ` · ${entry.resource_id}` : ""}`);
    orgCell(row, entry.outcome);
    orgCell(row, entry.request_id || "–");
    return row;
  });
  document.querySelector("#organization-audit-table tbody").replaceChildren(...rows);
}

function bindOrganizationPage() {
  bindInvitationDialog();
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
    await Promise.all([loadInvitations(), loadOrganizationOverview()]);
  });
  document.getElementById("organization-settings-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const response = await API.request("/organizations/current", {
      method: "PATCH",
      body: JSON.stringify({ name: document.getElementById("organization-name").value }),
    });
    if (!response.ok) return showToast("Không lưu được cài đặt tổ chức.", "error");
    showToast("Đã cập nhật tổ chức.", "success");
    await loadOrganization();
  });
}

function bindPolicyPage() {
  document.getElementById("policy-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const response = await API.request("/organizations/current/policy", {
      method: "PUT",
      body: JSON.stringify({
        default_candidate_auth_mode: document.getElementById("policy-auth-mode").value,
        min_extension_version: document.getElementById("policy-extension-version").value,
        require_extension: document.getElementById("policy-require-extension").checked,
        require_fullscreen: document.getElementById("policy-require-fullscreen").checked,
        require_camera: document.getElementById("policy-require-camera").checked,
        require_microphone: document.getElementById("policy-require-microphone").checked,
        require_screen_share: document.getElementById("policy-require-screen-share").checked,
        block_clipboard: document.getElementById("policy-block-clipboard").checked,
        max_focus_loss_seconds: Number(document.getElementById("policy-focus").value),
        retention_days: Number(document.getElementById("policy-retention").value),
      }),
    });
    showToast(
      response.ok ? "Đã lưu chính sách." : "Không lưu được chính sách.",
      response.ok ? "success" : "error",
    );
  });
  document.getElementById("policy-auth-mode").addEventListener(
    "change",
    syncOrganizationPolicyConstraints,
  );
}

function bindBreakGlassPage() {
  bindGrantDecisionDialog();
  document.getElementById("grant-decision-form").addEventListener("submit", grantAction);
}

function bindAuditPage() {
  document.getElementById("audit-filter-button").addEventListener(
    "click",
    () => loadOrganizationAudit(),
  );
  document.getElementById("audit-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadOrganizationAudit();
    }
  });
}

async function initializeOrganization() {
  if (redirectLegacyOrganizationHash()) return;
  const section = getOrganizationSection();
  const user = await API.requireAuth();
  if (!user) return;
  if (!API.hasCapability("org.members.read")) {
    window.location.replace("/ui/exams/overview");
    return;
  }
  if (section === "organization") {
    bindOrganizationPage();
    await Promise.all([
      loadOrganization(),
      loadOrganizationOverview(),
      loadMembers(),
      loadInvitations(),
    ]);
  } else if (section === "policy") {
    bindPolicyPage();
    await loadPolicy();
  } else if (section === "break-glass") {
    bindBreakGlassPage();
    await loadAccessGrants();
  } else if (section === "audit") {
    bindAuditPage();
    await loadOrganizationAudit();
  }
}

initializeOrganization().catch((error) => showToast(error.message, "error"));
