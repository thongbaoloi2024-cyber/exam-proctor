function renderOverviewDelta(id, value, noun) {
  const element = document.getElementById(id);
  if (!element) return;
  const number = Number(value || 0);
  element.className = `metric-delta ${number > 0 ? "positive" : number < 0 ? "negative" : "neutral"}`;
  element.textContent = number === 0
    ? `Không đổi so với kỳ trước`
    : `${number > 0 ? "+" : ""}${SystemUI.formatNumber(number)} ${noun} so với kỳ trước`;
}

function attentionItem(tone, title, description, href) {
  const item = document.createElement("a");
  item.className = `attention-item attention-${tone}`;
  item.href = href;
  const icon = document.createElement("span");
  icon.className = "attention-icon";
  icon.textContent = tone === "warning" ? "!" : tone === "danger" ? "×" : "✓";
  const content = document.createElement("span");
  const heading = document.createElement("strong");
  heading.textContent = title;
  const detail = document.createElement("small");
  detail.textContent = description;
  content.append(heading, detail);
  const arrow = document.createElement("span");
  arrow.textContent = "→";
  item.append(icon, content, arrow);
  return item;
}

function renderAttention(data) {
  const list = document.getElementById("system-attention-list");
  const items = [];
  if (data.totals.pending_access_grants > 0) {
    items.push(attentionItem(
      "warning",
      `${data.totals.pending_access_grants} yêu cầu break-glass đang chờ duyệt`,
      "Kiểm tra lý do, tổ chức và thời hạn của từng yêu cầu.",
      "/ui/system/security",
    ));
  }
  const suspended = data.totals.organizations - data.totals.active_organizations;
  if (suspended > 0) {
    items.push(attentionItem(
      "danger",
      `${suspended} tổ chức đang tạm khóa`,
      "Tài khoản thuộc các tổ chức này không thể bắt đầu phiên mới.",
      "/ui/system/organizations?status=suspended",
    ));
  }
  if (!items.length) {
    items.push(attentionItem(
      "success",
      "Không có cảnh báo ưu tiên",
      "Các trạng thái vận hành chính đang trong ngưỡng bình thường.",
      "/ui/system/audit",
    ));
  }
  list.replaceChildren(...items);
}

async function loadSystemOverview() {
  const days = Number(document.getElementById("overview-range").value);
  const data = await SystemUI.fetchJson(`/system/analytics/overview?days=${days}`);
  SystemUI.text("kpi-organizations", SystemUI.formatNumber(data.totals.active_organizations));
  SystemUI.text("kpi-users", SystemUI.formatNumber(data.totals.users));
  SystemUI.text("kpi-exams", SystemUI.formatNumber(data.totals.exams));
  SystemUI.text("kpi-sessions", SystemUI.formatNumber(data.totals.active_sessions));
  SystemUI.text("kpi-grants", SystemUI.formatNumber(data.totals.pending_access_grants));
  renderOverviewDelta("delta-organizations", data.deltas.organizations, "tổ chức mới");
  renderOverviewDelta("delta-users", data.deltas.users, "người dùng mới");
  renderOverviewDelta("delta-exams", data.deltas.exams, "kỳ thi mới");
  renderOverviewDelta("delta-sessions", data.deltas.sessions, "phiên mới");
  SystemUI.renderLineChart("sessions-line-chart", data.session_trend);
  SystemUI.renderDonutChart("organizations-donut-chart", data.organization_status);
  SystemUI.renderBarChart("exams-bar-chart", data.exam_status);
  SystemUI.renderBarChart("top-organizations-chart", data.top_organizations);
  renderAttention(data);
}

function formatBytes(value) {
  if (value < 0) return "Không đọc được";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = Number(value || 0);
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(index ? 1 : 0)} ${units[index]}`;
}

async function loadOperations() {
  const data = await SystemUI.fetchJson("/system/operations");
  const jobs = Object.entries(data.report_jobs).map(([key, value]) => `${key}: ${value}`).join(" · ") || "Không có job";
  const versions = Object.entries(data.extension_versions).map(([key, value]) => `${key}: ${value}`).join(" · ") || "Chưa có extension";
  const cards = [
    ["Database", `${data.database_status} · ${data.database_latency_ms} ms`, data.database_status === "healthy"],
    ["Redis", data.redis_status === "configured" ? "Đã cấu hình" : "Chưa cấu hình (single-worker)", data.redis_status === "configured"],
    ["Report queue", jobs, data.recent_report_failures === 0],
    ["Evidence storage", formatBytes(data.evidence_storage_bytes), data.evidence_storage_bytes >= 0],
    ["Phiên connected", data.sessions_connected, true],
    ["Extension versions", versions, true],
  ];
  document.getElementById("operations-grid").replaceChildren(...cards.map(([labelText, valueText, healthy]) => {
    const card = document.createElement("article");
    card.className = `operation-card ${healthy ? "operation-healthy" : "operation-warning"}`;
    const label = document.createElement("span"); label.className = "metric-label"; label.textContent = labelText;
    const value = document.createElement("strong"); value.textContent = valueText;
    card.append(label, value);
    return card;
  }));
}

async function initializeSystemOverview() {
  const user = await SystemUI.initialize();
  if (!user) return;
  document.getElementById("overview-range").addEventListener("change", () => {
    loadSystemOverview().catch((error) => showToast(error.message, "error"));
  });
  document.getElementById("refresh-operations").addEventListener("click", () => {
    loadOperations().catch((error) => showToast(error.message, "error"));
  });
  try {
    await Promise.all([loadSystemOverview(), loadOperations()]);
  } catch (error) {
    showToast(error.message, "error");
  }
}

initializeSystemOverview();
