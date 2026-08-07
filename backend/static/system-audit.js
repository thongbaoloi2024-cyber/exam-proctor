const auditState = { page: 1, pageSize: 20, organizations: new Map() };

function auditQuery() {
  const params = new URLSearchParams({
    page: String(auditState.page),
    page_size: String(auditState.pageSize),
    days: document.getElementById("audit-range").value,
    search: document.getElementById("audit-search").value.trim(),
  });
  const outcome = document.getElementById("audit-outcome-filter").value;
  const organization = document.getElementById("audit-organization-filter").value;
  if (outcome) params.set("outcome", outcome);
  if (organization) params.set("org_id", organization);
  return params;
}

function auditDescriptionItem(label, value) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = value || "–";
  row.append(term, detail);
  return row;
}

function prettyAuditJson(value) {
  if (!value) return "Không có dữ liệu";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch (error) {
    return value;
  }
}

function showAuditDetail(entry) {
  SystemUI.text("audit-detail-time", SystemUI.formatDate(entry.created_at, true));
  const description = document.getElementById("audit-detail-description");
  description.replaceChildren(
    auditDescriptionItem("Hành động", entry.action),
    auditDescriptionItem("Kết quả", SystemUI.statusLabel(entry.outcome)),
    auditDescriptionItem("Tài nguyên", `${entry.resource_type}${entry.resource_id ? ` · ${entry.resource_id}` : ""}`),
    auditDescriptionItem("Tổ chức", auditState.organizations.get(entry.org_id) || entry.org_id),
    auditDescriptionItem("Actor", entry.actor_role || entry.actor_user_id),
    auditDescriptionItem("Request ID", entry.request_id),
    auditDescriptionItem("IP", entry.ip_address),
    auditDescriptionItem("Lý do", entry.reason),
  );
  SystemUI.text("audit-before", prettyAuditJson(entry.before_json));
  SystemUI.text("audit-after", prettyAuditJson(entry.after_json));
  document.getElementById("audit-detail-dialog").showModal();
}

function renderAuditRows(entries) {
  const tbody = document.querySelector("#system-audit-table tbody");
  if (!entries.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.appendChild(SystemUI.empty("Không có sự kiện audit phù hợp."));
    row.appendChild(cell);
    tbody.replaceChildren(row);
    return;
  }
  tbody.replaceChildren(...entries.map((entry) => {
    const row = document.createElement("tr");
    SystemUI.cell(row, SystemUI.formatDate(entry.created_at, true));
    const actionCell = SystemUI.cell(row, entry.action, "audit-action-cell");
    actionCell.title = entry.action;
    SystemUI.cell(row, `${entry.resource_type}${entry.resource_id ? ` · ${entry.resource_id}` : ""}`, "truncate-cell");
    SystemUI.cell(row, auditState.organizations.get(entry.org_id) || entry.org_id || "Toàn hệ thống");
    const outcome = document.createElement("td");
    outcome.appendChild(SystemUI.badge(entry.outcome));
    row.appendChild(outcome);
    const action = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "table-action-button";
    button.textContent = "Xem";
    button.addEventListener("click", () => showAuditDetail(entry));
    action.appendChild(button);
    row.appendChild(action);
    return row;
  }));
}

function populateAuditOrganizations(organizations) {
  auditState.organizations = new Map(organizations.map((organization) => [organization.id, organization.name]));
  const select = document.getElementById("audit-organization-filter");
  select.replaceChildren(
    new Option("Tất cả tổ chức", ""),
    ...organizations.map((organization) => new Option(organization.name, organization.id)),
  );
}

async function loadAuditAnalytics() {
  const days = document.getElementById("audit-range").value;
  const data = await SystemUI.fetchJson(`/system/analytics/audit?days=${days}`);
  SystemUI.renderLineChart("audit-trend-chart", data.activity_trend);
  SystemUI.renderDonutChart("audit-outcome-chart", data.outcomes);
  SystemUI.renderBarChart("audit-actions-chart", data.action_categories);
}

async function loadAuditEntries() {
  const page = await SystemUI.fetchJson(`/system/audit/page?${auditQuery().toString()}`);
  renderAuditRows(page.items);
  SystemUI.renderPagination("audit-pagination", page.page, page.pages, (nextPage) => {
    auditState.page = nextPage;
    loadAuditEntries().catch((error) => showToast(error.message, "error"));
  });
}

async function initializeSystemAudit() {
  const user = await SystemUI.initialize("system.security.read");
  if (!user) return;
  try {
    const organizations = await SystemUI.fetchJson("/system/organizations");
    populateAuditOrganizations(organizations);
    await Promise.all([loadAuditAnalytics(), loadAuditEntries()]);
  } catch (error) {
    showToast(error.message, "error");
  }
  document.getElementById("audit-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    auditState.page = 1;
    loadAuditEntries().catch((error) => showToast(error.message, "error"));
  });
  document.getElementById("audit-range").addEventListener("change", () => {
    auditState.page = 1;
    Promise.all([loadAuditAnalytics(), loadAuditEntries()]).catch((error) => showToast(error.message, "error"));
  });
}

initializeSystemAudit();
