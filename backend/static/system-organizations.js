const organizationState = {
  page: 1,
  pageSize: 10,
  selected: null,
  nextStatus: null,
};

function organizationQuery() {
  const params = new URLSearchParams({
    page: String(organizationState.page),
    page_size: String(organizationState.pageSize),
    search: document.getElementById("organization-search").value.trim(),
    sort: document.getElementById("organization-sort").value,
  });
  const status = document.getElementById("organization-status").value;
  if (status) params.set("status", status);
  return params;
}

function openOrganizationStatusDialog(organization) {
  organizationState.selected = organization;
  organizationState.nextStatus = organization.status === "active" ? "suspended" : "active";
  const suspending = organizationState.nextStatus === "suspended";
  SystemUI.text("organization-status-title", suspending ? "Tạm khóa tổ chức" : "Mở khóa tổ chức");
  SystemUI.text(
    "organization-status-description",
    suspending
      ? `Các phiên đăng nhập của ${organization.name} sẽ bị thu hồi.`
      : `${organization.name} sẽ có thể tiếp tục sử dụng nền tảng.`,
  );
  document.getElementById("organization-status-reason").value = "";
  const submit = document.getElementById("organization-status-submit");
  submit.textContent = suspending ? "Tạm khóa" : "Mở khóa";
  submit.classList.toggle("danger-button", suspending);
  document.getElementById("organization-status-dialog").showModal();
}

function renderOrganizationRows(organizations) {
  const tbody = document.querySelector("#system-organizations-table tbody");
  if (!organizations.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.appendChild(SystemUI.empty("Không tìm thấy tổ chức phù hợp."));
    row.appendChild(cell);
    tbody.replaceChildren(row);
    return;
  }
  const rows = organizations.map((organization) => {
    const row = document.createElement("tr");
    const identity = document.createElement("td");
    const link = document.createElement("a");
    link.href = `/ui/system/organizations/${encodeURIComponent(organization.id)}`;
    link.className = "table-primary-link";
    link.textContent = organization.name;
    const slug = document.createElement("small");
    slug.textContent = organization.slug || organization.id;
    identity.append(link, slug);
    row.appendChild(identity);
    const statusCell = document.createElement("td");
    statusCell.appendChild(SystemUI.badge(organization.status));
    row.appendChild(statusCell);
    SystemUI.cell(row, SystemUI.formatNumber(organization.user_count));
    SystemUI.cell(row, SystemUI.formatNumber(organization.exam_count));
    SystemUI.cell(row, SystemUI.formatNumber(organization.active_session_count));
    SystemUI.cell(
      row,
      organization.quota_concurrent_sessions
        ? `${organization.active_session_count} / ${SystemUI.formatNumber(organization.quota_concurrent_sessions)}`
        : "Không giới hạn",
    );
    const actions = document.createElement("td");
    actions.className = "table-actions";
    const detail = document.createElement("a");
    detail.className = "icon-link";
    detail.href = `/ui/system/organizations/${encodeURIComponent(organization.id)}`;
    detail.textContent = "Chi tiết";
    const statusButton = document.createElement("button");
    statusButton.type = "button";
    statusButton.className = "table-action-button";
    statusButton.textContent = organization.status === "active" ? "Tạm khóa" : "Mở khóa";
    statusButton.addEventListener("click", () => openOrganizationStatusDialog(organization));
    actions.append(detail, statusButton);
    row.appendChild(actions);
    return row;
  });
  tbody.replaceChildren(...rows);
}

async function loadOrganizationDirectory() {
  const [overview, page] = await Promise.all([
    SystemUI.fetchJson("/system/overview"),
    SystemUI.fetchJson(`/system/organizations/page?${organizationQuery().toString()}`),
  ]);
  SystemUI.text("organization-total", SystemUI.formatNumber(overview.organizations));
  SystemUI.text("organization-active", SystemUI.formatNumber(overview.active_organizations));
  SystemUI.text("organization-suspended", SystemUI.formatNumber(overview.organizations - overview.active_organizations));
  renderOrganizationRows(page.items);
  SystemUI.renderPagination("organization-pagination", page.page, page.pages, (nextPage) => {
    organizationState.page = nextPage;
    loadOrganizationDirectory().catch((error) => showToast(error.message, "error"));
  });
}

async function createOrganization(event) {
  event.preventDefault();
  const submit = document.getElementById("create-organization-submit");
  const quota = document.getElementById("system-org-quota").value;
  SystemUI.setBusy(submit, true, "Đang tạo...");
  try {
    const body = await SystemUI.fetchJson("/system/organizations", {
      method: "POST",
      body: JSON.stringify({
        name: document.getElementById("system-org-name").value,
        admin_email: document.getElementById("system-org-admin").value,
        retention_days: Number(document.getElementById("system-org-retention").value),
        quota_concurrent_sessions: quota ? Number(quota) : null,
      }),
    });
    SystemUI.text("invitation-token", body.admin_invitation_token);
    document.getElementById("system-invitation-result").classList.remove("hidden");
    submit.classList.add("hidden");
    showToast("Đã tạo tổ chức và sinh token lời mời.", "success");
    organizationState.page = 1;
    await loadOrganizationDirectory();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    SystemUI.setBusy(submit, false);
  }
}

async function updateOrganizationStatus(event) {
  event.preventDefault();
  const submit = document.getElementById("organization-status-submit");
  SystemUI.setBusy(submit, true);
  try {
    await SystemUI.fetchJson(
      `/system/organizations/${encodeURIComponent(organizationState.selected.id)}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          status: organizationState.nextStatus,
          reason: document.getElementById("organization-status-reason").value,
        }),
      },
    );
    document.getElementById("organization-status-dialog").close();
    showToast("Đã cập nhật trạng thái tổ chức.", "success");
    await loadOrganizationDirectory();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    SystemUI.setBusy(submit, false);
  }
}

async function initializeSystemOrganizations() {
  const user = await SystemUI.initialize();
  if (!user) return;
  const initialStatus = new URLSearchParams(window.location.search).get("status");
  if (["active", "suspended"].includes(initialStatus)) {
    document.getElementById("organization-status").value = initialStatus;
  }
  document.getElementById("open-create-organization").addEventListener("click", () => {
    const form = document.getElementById("system-create-org");
    form.reset();
    document.getElementById("system-org-retention").value = "365";
    document.getElementById("system-invitation-result").classList.add("hidden");
    document.getElementById("create-organization-submit").classList.remove("hidden");
    document.getElementById("create-organization-dialog").showModal();
  });
  document.getElementById("organization-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    organizationState.page = 1;
    loadOrganizationDirectory().catch((error) => showToast(error.message, "error"));
  });
  document.getElementById("system-create-org").addEventListener("submit", createOrganization);
  document.getElementById("organization-status-form").addEventListener("submit", updateOrganizationStatus);
  document.getElementById("copy-invitation-token").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(document.getElementById("invitation-token").textContent);
      showToast("Đã sao chép token.", "success");
    } catch (error) {
      showToast("Trình duyệt không cho phép sao chép tự động. Hãy chọn và sao chép token thủ công.", "error");
    }
  });
  try {
    await loadOrganizationDirectory();
  } catch (error) {
    showToast(error.message, "error");
  }
}

initializeSystemOrganizations();
