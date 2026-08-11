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
let organizationMembers = [];
let organizationInvitations = [];
let organizationAccessGrants = [];
const memberTableState = TableUI.createState({ pageSize: 10, sortKey: "email" });
const invitationTableState = TableUI.createState({ pageSize: 10, sortKey: "created", sortDirection: "descending" });
const accessGrantTableState = TableUI.createState({ pageSize: 10, sortKey: "created", sortDirection: "descending" });
const organizationAuditState = TableUI.createState({ pageSize: 20, sortKey: "created_at", sortDirection: "descending" });
const MEMBER_SORT_COLUMNS = {
  email: (member) => member.email,
  role: (member) => member.role,
  status: (member) => member.membership_status,
};
const INVITATION_SORT_COLUMNS = {
  email: (invitation) => invitation.email,
  role: (invitation) => invitation.role,
  status: (invitation) => invitation.status,
  created: { value: (invitation) => invitation.created_at, type: "date" },
  expires: { value: (invitation) => invitation.expires_at, type: "date" },
};
const ACCESS_GRANT_SORT_COLUMNS = {
  requester: (grant) => grant.requester_email,
  reason: (grant) => grant.reason,
  scope: (grant) => grant.scope,
  created: { value: (grant) => grant.created_at, type: "date" },
  status: (grant) => grant.effective_status,
  expires: { value: (grant) => grant.expires_at, type: "date" },
};
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
  const organizationName = document.getElementById("organization-name");
  if (organizationName) organizationName.value = organization.name;
  const title = document.getElementById("sidebar-brand-title");
  const meta = document.getElementById("sidebar-brand-context");
  const metaText = `${SystemUI.statusLabel(organization.status)} · lưu trữ ${organization.retention_days} ngày`;
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
    ["Thành viên đang hoạt động", `${data.members_active}/${data.members_total}`],
    ["Tài khoản đã bật MFA", `${data.members_with_mfa}/${data.members_total}`],
    ["Lời mời đang chờ", data.pending_invitations],
    ["Kỳ thi", data.exams_total],
    ["Phiên đồng thời", `${data.sessions_active}/${data.concurrent_session_quota ?? "∞"}`],
    ["Thời hạn lưu trữ", `${data.retention_days} ngày`],
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
  organizationMembers = await response.json();
  renderMembers();
}

function renderMembers() {
  const tbody = document.querySelector("#members-table tbody");
  if (!organizationMembers.length) {
    TableUI.hidePagination("members-pagination");
    const row = document.createElement("tr");
    const cell = orgCell(row, "Chưa có thành viên.");
    cell.colSpan = 4;
    tbody.replaceChildren(row);
    return;
  }
  const sorted = TableUI.sortItems(organizationMembers, memberTableState, MEMBER_SORT_COLUMNS);
  const pageData = TableUI.paginate(sorted, memberTableState);
  const rows = pageData.items.map((member) => {
    const row = document.createElement("tr");
    const emailCell = orgCell(row, member.email);
    if (member.mfa_enabled) { const badge = document.createElement("span"); badge.className = "badge badge-low member-mfa-badge"; badge.textContent = "MFA"; emailCell.appendChild(badge); }
    const roleCell = document.createElement("td");
    const role = orgSelect(
      [["exam_manager", "Quản lý kỳ thi"], ["org_admin", "Quản trị tổ chức"]],
      member.role,
    );
    roleCell.appendChild(role);
    row.appendChild(roleCell);
    const statusCell = document.createElement("td");
    const memberStatus = orgSelect(
      [["active", "Đang hoạt động"], ["suspended", "Tạm khóa"], ["revoked", "Đã thu hồi"]],
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
  tbody.replaceChildren(...rows);
  TableUI.renderPagination("members-pagination", pageData, (nextPage) => {
    memberTableState.page = nextPage;
    renderMembers();
  });
}

async function loadInvitations() {
  const response = await API.request("/organizations/current/invitations");
  if (!response.ok) return;
  organizationInvitations = await response.json();
  renderInvitations();
}

function renderInvitations() {
  const tbody = document.querySelector("#invitations-table tbody");
  if (!organizationInvitations.length) {
    TableUI.hidePagination("invitations-pagination");
    const row = document.createElement("tr"); const cell = orgCell(row, "Không có lời mời."); cell.colSpan = 6; tbody.replaceChildren(row); return;
  }
  const sorted = TableUI.sortItems(organizationInvitations, invitationTableState, INVITATION_SORT_COLUMNS);
  const pageData = TableUI.paginate(sorted, invitationTableState);
  tbody.replaceChildren(...pageData.items.map((invitation) => {
    const row = document.createElement("tr");
    orgCell(row, invitation.email);
    orgCell(row, { exam_manager: "Quản lý kỳ thi", org_admin: "Quản trị tổ chức" }[invitation.role] || invitation.role);
    orgCell(row, SystemUI.statusLabel(invitation.status));
    orgCell(row, new Date(invitation.created_at).toLocaleString("vi-VN")); orgCell(row, new Date(invitation.expires_at).toLocaleString("vi-VN"));
    const action = document.createElement("td");
    if (invitation.status === "pending") { const revoke = document.createElement("button"); revoke.type = "button"; revoke.className = "secondary-button"; revoke.textContent = "Thu hồi"; revoke.addEventListener("click", () => revokeInvitation(invitation.id)); action.appendChild(revoke); }
    row.appendChild(action); return row;
  }));
  TableUI.renderPagination("invitations-pagination", pageData, (nextPage) => {
    invitationTableState.page = nextPage;
    renderInvitations();
  });
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
    ? "Phê duyệt quyền truy cập ngoại lệ"
    : "Thu hồi quyền truy cập ngoại lệ";
  document.getElementById("grant-decision-requester").textContent = grant.requester_email;
  document.getElementById("grant-decision-scope").textContent = `${grant.scope === "evidence.read" ? "Xem dữ liệu giám sát" : grant.scope} · ${grant.read_only ? "chỉ đọc" : "có thể chỉnh sửa"}`;
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
    showToast(body.detail || "Không cập nhật được quyền truy cập ngoại lệ.", "error");
    return;
  }
  document.getElementById("grant-decision-dialog").close();
  showToast(action === "approve" ? "Đã phê duyệt quyền chỉ đọc." : "Đã thu hồi quyền truy cập ngoại lệ.", "success");
  await loadAccessGrants();
}

async function loadAccessGrants() {
  const response = await API.request("/organizations/current/access-grants");
  if (!response.ok) return;
  organizationAccessGrants = await response.json();
  renderAccessGrants();
}

function renderAccessGrants() {
  const tbody = document.querySelector("#access-grants-table tbody");
  if (!organizationAccessGrants.length) {
    TableUI.hidePagination("access-grants-pagination");
    const row = document.createElement("tr");
    const cell = orgCell(row, "Không có yêu cầu quyền truy cập.");
    cell.colSpan = 7;
    tbody.replaceChildren(row);
    return;
  }
  const sorted = TableUI.sortItems(organizationAccessGrants, accessGrantTableState, ACCESS_GRANT_SORT_COLUMNS);
  const pageData = TableUI.paginate(sorted, accessGrantTableState);
  const rows = pageData.items.map((grant) => {
    const row = document.createElement("tr");
    orgCell(row, grant.requester_email);
    orgCell(row, grant.reason);
    orgCell(row, `${grant.scope === "evidence.read" ? "Xem dữ liệu giám sát" : grant.scope} · ${grant.read_only ? "Chỉ đọc" : "Có thể chỉnh sửa"}`);
    orgCell(row, new Date(grant.created_at).toLocaleString("vi-VN"));
    orgCell(row, SystemUI.statusLabel(grant.effective_status));
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
  tbody.replaceChildren(...rows);
  TableUI.renderPagination("access-grants-pagination", pageData, (nextPage) => {
    accessGrantTableState.page = nextPage;
    renderAccessGrants();
  });
}

function appendOrganizationAuditUserCell(row, entry) {
  const cell = document.createElement("td");
  cell.className = "audit-user-cell";
  const name = document.createElement("strong");
  name.textContent = entry.actor_display_name || entry.actor_email || "Hệ thống";
  cell.appendChild(name);
  if (entry.actor_email && entry.actor_email !== name.textContent) {
    const email = document.createElement("small");
    email.textContent = entry.actor_email;
    cell.appendChild(email);
  }
  row.appendChild(cell);
}

function appendOrganizationAuditOutcomeCell(row, outcome) {
  const cell = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = `status-badge status-${String(outcome || "neutral").replace(/[^a-z0-9_-]/gi, "")}`;
  badge.textContent = {
    success: "Thành công",
    failed: "Thất bại",
    denied: "Bị từ chối",
  }[outcome] || outcome || "Không xác định";
  cell.appendChild(badge);
  row.appendChild(cell);
}

function renderOrganizationAuditPagination(page) {
  const container = document.getElementById("organization-audit-pagination");
  const label = document.createElement("span");
  label.textContent = `Trang ${page.page} / ${page.pages} · ${page.total} sự kiện`;
  const actions = document.createElement("div");
  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "secondary-button pagination-button";
  previous.textContent = "← Trước";
  previous.disabled = page.page <= 1;
  previous.addEventListener("click", () => {
    organizationAuditState.page = page.page - 1;
    loadOrganizationAudit();
  });
  const next = document.createElement("button");
  next.type = "button";
  next.className = "secondary-button pagination-button";
  next.textContent = "Sau →";
  next.disabled = page.page >= page.pages;
  next.addEventListener("click", () => {
    organizationAuditState.page = page.page + 1;
    loadOrganizationAudit();
  });
  actions.append(previous, next);
  container.replaceChildren(label, actions);
}

async function loadOrganizationAudit() {
  const params = new URLSearchParams({
    page: String(organizationAuditState.page),
    page_size: String(organizationAuditState.pageSize),
    sort_by: organizationAuditState.sortKey,
    sort_order: organizationAuditState.sortDirection === "descending" ? "desc" : "asc",
  });
  const search = document.getElementById("audit-search").value.trim();
  const outcome = document.getElementById("audit-outcome").value;
  if (search) params.set("search", search);
  if (outcome) params.set("outcome", outcome);
  const response = await API.request(`/organizations/current/audit/page?${params}`);
  if (!response.ok) return;
  const page = await response.json();
  const rows = page.items.map((entry) => {
    const row = document.createElement("tr");
    orgCell(row, new Date(entry.created_at).toLocaleString("vi-VN"));
    appendOrganizationAuditUserCell(row, entry);
    orgCell(row, SystemUI.actionLabel(entry.action));
    orgCell(row, `${SystemUI.resourceLabel(entry.resource_type)}${entry.resource_id ? ` · ${entry.resource_id}` : ""}`);
    appendOrganizationAuditOutcomeCell(row, entry.outcome);
    orgCell(row, entry.reason || "–");
    return row;
  });
  const tbody = document.querySelector("#organization-audit-table tbody");
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = orgCell(row, "Không có hoạt động phù hợp.");
    cell.colSpan = 6;
    tbody.replaceChildren(row);
  } else {
    tbody.replaceChildren(...rows);
  }
  renderOrganizationAuditPagination(page);
}

function bindOrganizationPage() {
  TableUI.bindSort("members-table", memberTableState, renderMembers);
  TableUI.bindSort("invitations-table", invitationTableState, renderInvitations);
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
    result.textContent = `Mã lời mời (chỉ hiển thị lần này): ${body.invitation_token}`;
    document.getElementById("invitation-email").value = "";
    await Promise.all([loadInvitations(), loadOrganizationOverview()]);
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
  TableUI.bindSort("access-grants-table", accessGrantTableState, renderAccessGrants);
  bindGrantDecisionDialog();
  document.getElementById("grant-decision-form").addEventListener("submit", grantAction);
}

function bindAuditPage() {
  TableUI.bindSort("organization-audit-table", organizationAuditState, () => {
    loadOrganizationAudit().catch((error) => showToast(error.message, "error"));
  });
  document.getElementById("audit-filter-button").addEventListener(
    "click",
    () => {
      organizationAuditState.page = 1;
      loadOrganizationAudit();
    },
  );
  document.getElementById("audit-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      organizationAuditState.page = 1;
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
