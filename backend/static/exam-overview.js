const WORKSPACE_STATUS_LABELS = {
  draft: "Bản nháp",
  scheduled: "Đã lên lịch",
  open: "Đang mở",
  closed: "Đã đóng",
  archived: "Lưu trữ",
};
const WORKSPACE_ROLE_LABELS = {
  owner: "Chủ kỳ thi",
  manager: "Quản lý",
  proctor: "Giám thị",
};

function workspaceChartItems(values, labels) {
  return Object.entries(values || {}).map(([key, value]) => ({
    key,
    label: labels[key] || key,
    value,
  }));
}

function workspaceAttention(item) {
  const link = document.createElement("a");
  const dangerous = item.alert_sessions > 0 || item.disconnected_sessions > 0;
  link.className = `attention-item attention-${dangerous ? "danger" : "warning"}`;
  link.href = dangerous || !item.allowed_actions.includes("exam.manage")
    ? `/ui/exams/${encodeURIComponent(item.id)}/detail`
    : `/ui/exams/${encodeURIComponent(item.id)}/detail?tab=manage`;
  const icon = document.createElement("span");
  icon.className = "attention-icon";
  icon.textContent = "!";
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = item.name;
  const detail = document.createElement("small");
  detail.textContent = item.attention.join(" · ");
  copy.append(title, detail);
  const arrow = document.createElement("span");
  arrow.textContent = "→";
  link.append(icon, copy, arrow);
  return link;
}

function workspaceSuccessAttention() {
  const link = document.createElement("a");
  link.className = "attention-item attention-success";
  link.href = "/ui/exams";
  const icon = document.createElement("span");
  icon.className = "attention-icon";
  icon.textContent = "✓";
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = "Không có kỳ thi cần xử lý ngay";
  const detail = document.createElement("small");
  detail.textContent = "Các assignment hiện không có cảnh báo vận hành nổi bật.";
  copy.append(title, detail);
  const arrow = document.createElement("span");
  arrow.textContent = "→";
  link.append(icon, copy, arrow);
  return link;
}

function workspaceCell(row, value) {
  const cell = document.createElement("td");
  if (value instanceof Node) cell.appendChild(value);
  else cell.textContent = value == null || value === "" ? "–" : String(value);
  row.appendChild(cell);
  return cell;
}

function renderWorkspaceItems(items) {
  const body = document.getElementById("workspace-exams-body");
  if (!items.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "empty-state-cell";
    cell.textContent = "Bạn chưa có kỳ thi nào được phân công. Có thể tạo kỳ thi mới từ trang Kỳ thi.";
    row.appendChild(cell);
    body.replaceChildren(row);
    return;
  }
  const rows = items.map((item) => {
    const row = document.createElement("tr");
    const examCopy = document.createElement("span");
    examCopy.className = "overview-exam-copy";
    const name = document.createElement("strong");
    name.textContent = item.name;
    const schedule = document.createElement("small");
    schedule.textContent = item.scheduled_start_at
      ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.scheduled_start_at))
      : "Chưa đặt lịch";
    examCopy.append(name, schedule);
    workspaceCell(row, examCopy);
    workspaceCell(row, WORKSPACE_ROLE_LABELS[item.assignment_role] || item.assignment_role);
    workspaceCell(row, SystemUI.badge(item.status, WORKSPACE_STATUS_LABELS[item.status] || item.status));
    workspaceCell(row, `${item.active_sessions} hoạt động`);
    const attention = document.createElement("span");
    attention.className = item.attention.length ? "overview-attention-text" : "muted";
    attention.textContent = item.attention.length ? item.attention.join(" · ") : "Ổn định";
    workspaceCell(row, attention);
    const action = document.createElement("a");
    const canManage = item.allowed_actions.includes("exam.manage");
    const monitorFirst = item.active_sessions || item.alert_sessions || item.disconnected_sessions;
    action.href = monitorFirst || !canManage
      ? `/ui/exams/${encodeURIComponent(item.id)}/detail`
      : `/ui/exams/${encodeURIComponent(item.id)}/detail?tab=manage`;
    action.className = "text-link";
    action.textContent = monitorFirst || !canManage ? "Theo dõi →" : "Quản lý →";
    workspaceCell(row, action);
    return row;
  });
  body.replaceChildren(...rows);
}

async function initializeExamOverview() {
  const user = await API.requireAuth();
  if (!user) return;
  const role = API.getRole();
  if (role === "system_admin") {
    window.location.replace("/ui/system");
    return;
  }
  if (role === "org_admin" || role === "admin") {
    window.location.replace("/ui/organization/overview");
    return;
  }
  const response = await API.request("/exams/workspace/overview");
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Không tải được tổng quan kỳ thi.");
  SystemUI.text("workspace-kpi-exams", SystemUI.formatNumber(data.assigned_exams_total));
  SystemUI.text("workspace-caption-exams", `${data.managed_exams} quản lý · ${data.proctored_exams} giám thị`);
  SystemUI.text("workspace-kpi-ready", `${data.open_exams}/${data.scheduled_exams}`);
  SystemUI.text("workspace-kpi-sessions", SystemUI.formatNumber(data.active_sessions));
  SystemUI.text("workspace-kpi-alerts", SystemUI.formatNumber(data.alert_sessions));
  SystemUI.text("workspace-caption-alerts", `${data.disconnected_sessions} phiên mất kết nối`);
  SystemUI.text("workspace-kpi-reviews", SystemUI.formatNumber(data.open_reviews));
  const roleSummary = data.managed_exams && data.proctored_exams
    ? "Bạn đang quản lý một số kỳ thi và làm giám thị ở các kỳ thi khác."
    : data.managed_exams
      ? "Không gian làm việc dành cho các kỳ thi bạn sở hữu hoặc quản lý."
      : "Không gian giám thị dành cho các kỳ thi được phân công.";
  SystemUI.text("workspace-role-summary", roleSummary);
  SystemUI.renderBarChart(
    "workspace-status-chart",
    workspaceChartItems(data.exam_status, WORKSPACE_STATUS_LABELS),
  );
  SystemUI.renderDonutChart(
    "workspace-role-chart",
    workspaceChartItems(data.assignment_roles, WORKSPACE_ROLE_LABELS),
  );
  const attentionItems = data.items.filter((item) => item.attention.length).map(workspaceAttention);
  document.getElementById("workspace-attention-list").replaceChildren(
    ...(attentionItems.length ? attentionItems.slice(0, 6) : [workspaceSuccessAttention()]),
  );
  renderWorkspaceItems(data.items);
}

initializeExamOverview().catch((error) => showToast(error.message, "error"));
