const ORGANIZATION_STATUS_LABELS = {
  draft: "Bản nháp",
  scheduled: "Đã lên lịch",
  open: "Đang mở",
  closed: "Đã đóng",
  archived: "Lưu trữ",
  pending: "Chờ kết nối",
  active: "Đang hoạt động",
  disconnected: "Mất kết nối",
  ended: "Đã kết thúc",
};

function organizationChartItems(values) {
  return Object.entries(values || {}).map(([key, value]) => ({
    key,
    label: ORGANIZATION_STATUS_LABELS[key] || key,
    value,
  }));
}

function organizationAttention(tone, titleText, detailText, href) {
  const link = document.createElement("a");
  link.className = `attention-item attention-${tone}`;
  link.href = href;
  const icon = document.createElement("span");
  icon.className = "attention-icon";
  icon.textContent = tone === "success" ? "✓" : "!";
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = titleText;
  const detail = document.createElement("small");
  detail.textContent = detailText;
  copy.append(title, detail);
  const arrow = document.createElement("span");
  arrow.textContent = "→";
  link.append(icon, copy, arrow);
  return link;
}

function renderOrganizationAttention(data) {
  const items = [];
  const missingMfa = Math.max(0, data.members_active - data.members_with_mfa);
  if (data.pending_invitations) {
    items.push(organizationAttention(
      "warning",
      `${data.pending_invitations} lời mời đang chờ`,
      "Kiểm tra thời hạn hoặc thu hồi lời mời không còn cần thiết.",
      "/ui/organization",
    ));
  }
  if (data.members_suspended) {
    items.push(organizationAttention(
      "warning",
      `${data.members_suspended} thành viên bị tạm khóa hoặc thu hồi`,
      "Rà soát trạng thái tài khoản và quyền truy cập.",
      "/ui/organization",
    ));
  }
  if (missingMfa) {
    items.push(organizationAttention(
      "danger",
      `${missingMfa} thành viên hoạt động chưa bật MFA`,
      "Khuyến nghị hoàn tất MFA cho các tài khoản quản trị và vận hành.",
      "/ui/organization",
    ));
  }
  if (data.quota_usage_percent != null && data.quota_usage_percent >= 80) {
    items.push(organizationAttention(
      data.quota_usage_percent >= 100 ? "danger" : "warning",
      `Đang dùng ${data.quota_usage_percent}% quota phiên đồng thời`,
      "Theo dõi các kỳ thi đang mở để tránh vượt hạn mức.",
      "/ui/organization/policy",
    ));
  }
  if (!items.length) {
    items.push(organizationAttention(
      "success",
      "Không có cảnh báo quản trị nổi bật",
      "Thành viên, lời mời và quota hiện trong trạng thái ổn định.",
      "/ui/organization/audit",
    ));
  }
  document.getElementById("organization-attention-list").replaceChildren(...items);
}

async function initializeOrganizationOverview() {
  const user = await API.requireAuth();
  if (!user) return;
  if (!API.hasCapability("org.members.read")) {
    window.location.replace(API.getRole() === "system_admin" ? "/ui/system" : "/ui/exams/overview");
    return;
  }
  const [organizationResponse, overviewResponse] = await Promise.all([
    API.request("/organizations/current"),
    API.request("/organizations/current/overview"),
  ]);
  if (!organizationResponse.ok || !overviewResponse.ok) {
    throw new Error("Không tải được tổng quan tổ chức.");
  }
  const organization = await organizationResponse.json();
  const data = await overviewResponse.json();
  document.getElementById("organization-overview-name").textContent = organization.name;
  const brandTitle = document.getElementById("sidebar-brand-title");
  if (brandTitle) brandTitle.textContent = organization.name;
  SystemUI.text("org-kpi-members", `${data.members_active}/${data.members_total}`);
  SystemUI.text("org-caption-members", `${data.members_suspended} tài khoản tạm khóa hoặc thu hồi`);
  const mfaPercent = data.members_active
    ? Math.round(Math.min(data.members_with_mfa, data.members_active) / data.members_active * 100)
    : 100;
  SystemUI.text("org-kpi-mfa", `${mfaPercent}%`);
  SystemUI.text("org-caption-mfa", `${data.members_with_mfa}/${data.members_active} thành viên hoạt động`);
  SystemUI.text("org-kpi-exams", SystemUI.formatNumber(data.exams_total));
  SystemUI.text("org-kpi-sessions", `${data.sessions_active}/${data.concurrent_session_quota ?? "∞"}`);
  SystemUI.text(
    "org-caption-sessions",
    data.quota_usage_percent == null ? "Không giới hạn quota" : `${data.quota_usage_percent}% quota đồng thời`,
  );
  SystemUI.text("org-kpi-invitations", SystemUI.formatNumber(data.pending_invitations));
  SystemUI.renderBarChart("organization-exam-chart", organizationChartItems(data.exam_status));
  SystemUI.renderDonutChart("organization-session-chart", organizationChartItems(data.session_status));
  renderOrganizationAttention(data);
}

initializeOrganizationOverview().catch((error) => showToast(error.message, "error"));
