const securityState = { page: 1, pageSize: 10, organizations: [] };

function grantQuery() {
  const params = new URLSearchParams({
    page: String(securityState.page),
    page_size: String(securityState.pageSize),
  });
  const status = document.getElementById("security-status-filter").value;
  const organization = document.getElementById("security-organization-filter").value;
  if (status) params.set("status", status);
  if (organization) params.set("org_id", organization);
  return params;
}

function populateSecurityOrganizations(organizations) {
  const filter = document.getElementById("security-organization-filter");
  const request = document.getElementById("security-request-organization");
  const filterOptions = [new Option("Tất cả tổ chức", "")];
  const requestOptions = [new Option("Chọn tổ chức", "")];
  organizations.forEach((organization) => {
    filterOptions.push(new Option(organization.name, organization.id));
    const option = new Option(organization.name, organization.id);
    option.disabled = organization.status !== "active";
    requestOptions.push(option);
  });
  filter.replaceChildren(...filterOptions);
  request.replaceChildren(...requestOptions);
}

function renderSecurityRows(grants) {
  const tbody = document.querySelector("#security-grants-table tbody");
  if (!grants.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.appendChild(SystemUI.empty("Không có yêu cầu phù hợp."));
    row.appendChild(cell);
    tbody.replaceChildren(row);
    return;
  }
  tbody.replaceChildren(...grants.map((grant) => {
    const row = document.createElement("tr");
    const organization = document.createElement("td");
    const link = document.createElement("a");
    link.href = `/ui/system/organizations/${encodeURIComponent(grant.org_id)}`;
    link.className = "table-primary-link";
    link.textContent = grant.organization_name;
    organization.appendChild(link);
    if (grant.effective_status === "active") {
      const evidenceLink = document.createElement("a");
      evidenceLink.href = "/ui/system/evidence";
      evidenceLink.className = "metric-link";
      evidenceLink.textContent = "Xem dữ liệu được cấp quyền →";
      organization.appendChild(evidenceLink);
    }
    row.appendChild(organization);
    SystemUI.cell(row, grant.requester_email);
    const reason = SystemUI.cell(row, grant.reason, "truncate-cell");
    reason.title = grant.reason;
    const statusCell = document.createElement("td");
    statusCell.appendChild(SystemUI.badge(grant.effective_status));
    row.appendChild(statusCell);
    SystemUI.cell(row, SystemUI.formatDate(grant.created_at, true));
    SystemUI.cell(row, SystemUI.formatDate(grant.expires_at, true));
    return row;
  }));
}

async function loadSecurityAnalytics() {
  const data = await SystemUI.fetchJson("/system/analytics/security?days=30");
  data.status_totals.forEach((item) => {
    const element = document.querySelector(`[data-status-kpi="${item.key}"]`);
    if (element) element.textContent = SystemUI.formatNumber(item.value);
  });
  SystemUI.renderLineChart("security-trend-chart", data.request_trend);
  SystemUI.renderDonutChart("security-status-chart", data.status_totals);
}

async function loadSecurityGrants() {
  const page = await SystemUI.fetchJson(`/system/access-grants?${grantQuery().toString()}`);
  renderSecurityRows(page.items);
  SystemUI.renderPagination("security-pagination", page.page, page.pages, (nextPage) => {
    securityState.page = nextPage;
    loadSecurityGrants().catch((error) => showToast(error.message, "error"));
  });
}

async function submitSecurityRequest(event) {
  event.preventDefault();
  const submit = event.submitter;
  SystemUI.setBusy(submit, true, "Đang gửi...");
  try {
    await SystemUI.fetchJson("/system/access-grants", {
      method: "POST",
      body: JSON.stringify({
        org_id: document.getElementById("security-request-organization").value,
        reason: document.getElementById("security-request-reason").value,
        scope: "evidence.read",
        requested_duration_minutes: Number(document.getElementById("security-request-duration").value),
      }),
    });
    document.getElementById("security-request-dialog").close();
    event.target.reset();
    showToast("Đã gửi yêu cầu; đang chờ Organization Admin phê duyệt.", "success");
    await Promise.all([loadSecurityAnalytics(), loadSecurityGrants()]);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    SystemUI.setBusy(submit, false);
  }
}

async function initializeSystemSecurity() {
  const user = await SystemUI.initialize("system.security.read");
  if (!user) return;
  try {
    securityState.organizations = await SystemUI.fetchJson("/system/organizations");
    populateSecurityOrganizations(securityState.organizations);
    await Promise.all([loadSecurityAnalytics(), loadSecurityGrants()]);
  } catch (error) {
    showToast(error.message, "error");
  }
  document.getElementById("security-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    securityState.page = 1;
    loadSecurityGrants().catch((error) => showToast(error.message, "error"));
  });
  document.getElementById("open-break-glass-request").addEventListener("click", () => {
    document.getElementById("security-request-form").reset();
    document.getElementById("security-request-dialog").showModal();
  });
  document.getElementById("security-request-form").addEventListener("submit", submitSecurityRequest);
}

initializeSystemSecurity();
