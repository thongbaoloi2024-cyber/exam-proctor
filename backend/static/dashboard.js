const dashboardRoot = document.getElementById("dashboard-root");
const EXAM_ID = dashboardRoot.dataset.examId;
const sessionData = new Map();
const TABLE_PAGE_SIZE = 10;
let initialLoadDone = false;
let lastUpdatedId = null;
let reconnectTimer = null;
let refreshTimer = null;
let canEndSessions = false;
let canResetSessions = false;
let endingSessionId = null;
let dashboardExam = null;
let sessionPage = 1;
let incidentPage = 1;
let incidentData = [];
const SEVERITY_LABELS = { LOW: "Thông tin", MEDIUM: "Cảnh báo", HIGH: "Nghiêm trọng" };
const VIOLATION_LABELS = {
  FACE_ABSENT: "Vắng mặt",
  MULTIPLE_FACES: "Nhiều người",
  EYES_CLOSED: "Nhắm mắt kéo dài",
  GAZE_AWAY: "Nhìn lệch khỏi màn hình",
  TALKING: "Nói chuyện",
  OBJECT_DETECTED: "Phát hiện vật thể cấm",
  HEAD_POSE_AWAY: "Quay đầu khỏi màn hình",
  IDENTITY_MISMATCH: "Nghi ngờ đổi người",
};

function stateBadgeInfo(status, sessionState) {
  if (status === "ended") return { cls: "badge-ended", label: "KẾT THÚC" };
  if (status === "disconnected") return { cls: "badge-medium", label: "MẤT KẾT NỐI" };
  if (status === "pending") return { cls: "badge-medium", label: "CHỜ KẾT NỐI" };
  if (sessionState === "SESSION_ALERT") return { cls: "badge-high", label: "CẢNH BÁO" };
  return { cls: "badge-low", label: "BÌNH THƯỜNG" };
}

function appendTextCell(row, text) {
  const cell = document.createElement("td");
  cell.textContent = String(text);
  row.appendChild(cell);
  return cell;
}

function showTableMessage(tbody, message, columns = 7) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.className = "muted";
  cell.textContent = message;
  row.appendChild(cell);
  tbody.replaceChildren(row);
}

function paginateItems(items, requestedPage) {
  const totalPages = Math.max(1, Math.ceil(items.length / TABLE_PAGE_SIZE));
  const page = Math.min(Math.max(1, requestedPage), totalPages);
  const start = (page - 1) * TABLE_PAGE_SIZE;
  return {
    items: items.slice(start, start + TABLE_PAGE_SIZE),
    page,
    totalPages,
    firstItem: items.length ? start + 1 : 0,
    lastItem: Math.min(start + TABLE_PAGE_SIZE, items.length),
  };
}

function hidePagination(containerId) {
  const container = document.getElementById(containerId);
  container.classList.add("hidden");
  container.replaceChildren();
}

function renderPagination(containerId, pageData, totalItems, onPageChange) {
  const container = document.getElementById(containerId);
  if (!totalItems) return hidePagination(containerId);
  const label = document.createElement("span");
  label.textContent = `Hiển thị ${pageData.firstItem}–${pageData.lastItem} / ${totalItems} · Trang ${pageData.page} / ${pageData.totalPages}`;
  const actions = document.createElement("div");
  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "secondary-button pagination-button";
  previous.textContent = "← Trước";
  previous.disabled = pageData.page <= 1;
  previous.addEventListener("click", () => onPageChange(pageData.page - 1));
  const next = document.createElement("button");
  next.type = "button";
  next.className = "secondary-button pagination-button";
  next.textContent = "Sau →";
  next.disabled = pageData.page >= pageData.totalPages;
  next.addEventListener("click", () => onPageChange(pageData.page + 1));
  actions.append(previous, next);
  container.replaceChildren(label, actions);
  container.classList.remove("hidden");
}

function renderKpis() {
  const all = [...sessionData.values()];
  const active = all.filter((session) => session.status === "active");
  const alerting = active.filter((session) => session.sessionState === "SESSION_ALERT").length;
  const avgRisk = active.length ? active.reduce((sum, item) => sum + item.riskScore, 0) / active.length : 0;
  const disconnected = all.filter((session) => session.status === "disconnected").length;
  const deviceIssues = active.filter((session) => [session.cameraStatus, session.microphoneStatus, session.screenShareStatus].includes("issue")).length;
  const tiles = [
    ["Đang tham gia", active.length, false],
    ["Đang cảnh báo", alerting, alerting > 0],
    ["Rủi ro trung bình", avgRisk.toFixed(1), false],
    ["Lỗi thiết bị", deviceIssues, deviceIssues > 0],
    ["Mất kết nối", disconnected, disconnected > 0],
  ];
  document.getElementById("kpi-row").replaceChildren(...tiles.map(([labelText, valueText, alert]) => {
    const wrapper = document.createElement("div");
    wrapper.className = `kpi-tile${alert ? " kpi-alert" : ""}`;
    const value = document.createElement("div"); value.className = "kpi-value"; value.textContent = valueText;
    const label = document.createElement("div"); label.className = "kpi-label"; label.textContent = labelText;
    wrapper.append(value, label); return wrapper;
  }));
}

function statusText(value, label) {
  const names = { ready: "sẵn sàng", issue: "lỗi", pending: "đang chờ", unknown: "chưa rõ", not_required: "không yêu cầu" };
  return `${label}: ${names[value] || value || "chưa rõ"}`;
}

function formatLastSeen(value) {
  if (!value) return "Chưa có cập nhật";
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s trước`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} phút trước`;
  return new Date(value).toLocaleString("vi-VN");
}

function formatExamHeaderDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "–";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function renderExamDetailHeader(exam) {
  const statusLabels = {
    draft: "Bản nháp",
    scheduled: "Đã lên lịch",
    open: "Đang mở",
    closed: "Đã đóng",
    archived: "Đã lưu trữ",
  };
  document.getElementById("detail-exam-title").textContent = exam.name;
  document.getElementById("detail-created-at").textContent = formatExamHeaderDate(exam.created_at);
  document.getElementById("detail-updated-at").textContent = formatExamHeaderDate(exam.updated_at);
  const status = document.getElementById("detail-status");
  status.className = `exam-status-badge status-${exam.status}`;
  status.textContent = statusLabels[exam.status] || exam.status;
  const canClose = (exam.allowed_actions || []).includes("exam.manage")
    && exam.status === "open"
    && (exam.allowed_transitions || []).includes("closed");
  document.getElementById("detail-close-exam").classList.toggle("hidden", !canClose);
  const joinCode = document.getElementById("detail-join-code");
  joinCode.textContent = exam.join_code || "Đã ẩn";
  joinCode.disabled = !exam.join_code;
  joinCode.title = exam.join_code
    ? `Nhấn để sao chép · Hết hạn ${formatExamHeaderDate(exam.join_code_expires_at)}`
    : "Mã tham gia đã được ẩn";
  document.title = `${exam.name} · Giám Thị Số`;
}

async function copyDashboardJoinCode() {
  if (!dashboardExam?.join_code) return;
  try {
    await navigator.clipboard.writeText(dashboardExam.join_code);
    showToast(`Đã sao chép mã tham gia: ${dashboardExam.join_code}`, "success");
  } catch (error) {
    showToast(`Mã tham gia: ${dashboardExam.join_code} (trình duyệt không hỗ trợ tự chép)`, "info");
  }
}

async function closeDashboardExam() {
  if (!dashboardExam) return;
  const button = document.getElementById("detail-close-exam");
  button.disabled = true;
  const response = await API.request(`/exams/${encodeURIComponent(EXAM_ID)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status: "closed", expected_version: dashboardExam.version }),
  });
  const body = await response.json().catch(() => ({}));
  button.disabled = false;
  if (!response.ok) {
    showToast(typeof body.detail === "string" ? body.detail : "Không đóng được kỳ thi.", "error");
    return;
  }
  dashboardExam = body;
  renderExamDetailHeader(dashboardExam);
  showToast("Đã đóng kỳ thi.", "success");
}

function filteredSessions() {
  const query = document.getElementById("session-search").value.trim().toLocaleLowerCase("vi");
  const status = document.getElementById("session-status-filter").value;
  const sort = document.getElementById("session-sort").value;
  const items = [...sessionData.entries()].filter(([, session]) => {
    const haystack = `${session.studentName} ${session.candidateIdentity || ""}`.toLocaleLowerCase("vi");
    if (query && !haystack.includes(query)) return false;
    if (status === "all") return true;
    if (status === "alert") return session.sessionState === "SESSION_ALERT" || session.integrityStatus === "alert";
    return session.status === status;
  });
  const priority = (item) => (item.sessionState === "SESSION_ALERT" ? 4 : 0) + (item.integrityStatus === "alert" ? 2 : 0) + ([item.cameraStatus, item.microphoneStatus, item.screenShareStatus].includes("issue") ? 1 : 0);
  items.sort(([, a], [, b]) => {
    if (sort === "risk") return b.riskScore - a.riskScore;
    if (sort === "name") return a.studentName.localeCompare(b.studentName, "vi");
    if (sort === "recent") return new Date(b.lastSeenAt || 0) - new Date(a.lastSeenAt || 0);
    return priority(b) - priority(a) || b.riskScore - a.riskScore;
  });
  return items;
}

function renderTable() {
  const tbody = document.querySelector("#sessions-table tbody");
  if (!initialLoadDone) {
    hidePagination("session-pagination");
    return showTableMessage(tbody, "Đang tải...");
  }
  const items = filteredSessions();
  if (!items.length) {
    hidePagination("session-pagination");
    return showTableMessage(tbody, sessionData.size ? "Không có phiên phù hợp bộ lọc." : "Chưa có thí sinh nào tham gia kỳ thi này.");
  }
  const pageData = paginateItems(items, sessionPage);
  sessionPage = pageData.page;
  const rows = pageData.items.map(([id, session]) => {
    const row = document.createElement("tr");
    if (id === lastUpdatedId) row.classList.add("updated");
    appendTextCell(row, session.studentName);
    appendTextCell(row, session.candidateIdentity || "-");
    const client = session.clientType === "browser_extension"
      ? `${session.browserName || "Trình duyệt"} ${session.browserVersion || ""} · Tiện ích ${session.extensionVersion || "-"}`
      : "Ứng dụng giám sát máy tính";
    appendTextCell(row, `${session.authenticationMethod === "google" ? "Google" : "Thủ công"} · ${client}${session.platform ? ` · ${session.platform}` : ""}`);
    const statusCell = document.createElement("td");
    const badgeInfo = stateBadgeInfo(session.status, session.sessionState);
    const badge = document.createElement("span"); badge.className = `badge ${badgeInfo.cls}`; badge.textContent = badgeInfo.label;
    const seen = document.createElement("small"); seen.className = "muted dashboard-last-seen"; seen.textContent = formatLastSeen(session.lastSeenAt);
    if (session.disconnectReason) seen.title = session.disconnectReason;
    statusCell.append(badge, seen); row.appendChild(statusCell);
    appendTextCell(row, session.riskScore.toFixed(1));
    const integrityCell = document.createElement("td");
    const integrityBadge = document.createElement("span");
    integrityBadge.className = `badge ${session.integrityStatus === "alert" ? "badge-high" : session.integrityStatus === "warning" ? "badge-medium" : "badge-low"}`;
    integrityBadge.textContent = `${{ healthy: "Ổn định", warning: "Cảnh báo", alert: "Nguy cơ" }[session.integrityStatus] || session.integrityStatus} · ${session.browserEventCount} sự kiện`;
    const devices = document.createElement("small"); devices.className = "muted device-status-line";
    devices.textContent = [statusText(session.cameraStatus, "Camera"), statusText(session.microphoneStatus, "Micrô"), statusText(session.screenShareStatus, "Màn hình")].join(" · ");
    integrityCell.append(integrityBadge, devices); row.appendChild(integrityCell);
    const actions = document.createElement("td"); actions.className = "table-actions";
    const actionGroup = document.createElement("div"); actionGroup.className = "table-actions-inner";
    const detail = document.createElement("a"); detail.href = `/ui/exams/${encodeURIComponent(EXAM_ID)}/sessions/${encodeURIComponent(id)}`; detail.textContent = "Chi tiết";
    actionGroup.appendChild(detail);
    if (canEndSessions && session.status !== "ended") {
      const end = document.createElement("button"); end.type = "button"; end.className = "link-button danger-text"; end.textContent = "Kết thúc";
      end.addEventListener("click", () => openEndDialog(id, session.studentName)); actionGroup.appendChild(end);
    }
    if (canResetSessions && ["ended", "disconnected"].includes(session.status)) {
      const reset = document.createElement("button"); reset.type = "button"; reset.className = "link-button"; reset.textContent = "Cấp lại phiên";
      reset.addEventListener("click", () => resetSession(id, session.studentName)); actionGroup.appendChild(reset);
    }
    actions.appendChild(actionGroup); row.appendChild(actions); return row;
  });
  tbody.replaceChildren(...rows);
  renderPagination("session-pagination", pageData, items.length, (nextPage) => {
    sessionPage = nextPage;
    renderTable();
  });
}

function renderAll() { renderKpis(); renderTable(); }
function safeNumber(value, fallback = 0) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }

function upsertSession(id, base = {}) {
  const old = sessionData.get(id) || {};
  sessionData.set(id, {
    studentName: base.studentName ?? old.studentName ?? "-", candidateIdentity: base.candidateIdentity ?? old.candidateIdentity ?? null,
    sessionState: base.sessionState ?? old.sessionState ?? "SESSION_NORMAL", riskScore: safeNumber(base.riskScore, old.riskScore ?? 0),
    status: base.status ?? old.status ?? "active", authenticationMethod: base.authenticationMethod ?? old.authenticationMethod ?? "manual",
    clientType: base.clientType ?? old.clientType ?? "desktop_cv", extensionVersion: base.extensionVersion ?? old.extensionVersion ?? null,
    browserName: base.browserName ?? old.browserName ?? null, browserVersion: base.browserVersion ?? old.browserVersion ?? null,
    platform: base.platform ?? old.platform ?? null, lastSeenAt: base.lastSeenAt ?? old.lastSeenAt ?? null,
    disconnectReason: base.disconnectReason ?? old.disconnectReason ?? null,
    integrityScore: safeNumber(base.integrityScore, old.integrityScore ?? 0), integrityStatus: base.integrityStatus ?? old.integrityStatus ?? "healthy",
    browserEventCount: Number.isFinite(Number(base.browserEventCount)) ? Number(base.browserEventCount) : old.browserEventCount ?? 0,
    cameraStatus: base.cameraStatus ?? old.cameraStatus ?? "unknown", microphoneStatus: base.microphoneStatus ?? old.microphoneStatus ?? "unknown",
    screenShareStatus: base.screenShareStatus ?? old.screenShareStatus ?? "unknown",
    resetCount: Number.isFinite(Number(base.resetCount)) ? Number(base.resetCount) : old.resetCount ?? 0,
  });
  lastUpdatedId = id; renderAll();
}

async function loadInitialSessions() {
  const response = await API.request(`/exams/${encodeURIComponent(EXAM_ID)}/sessions`);
  if (!response.ok) throw new Error("Không tải được danh sách phiên.");
  const sessions = await response.json();
  sessions.forEach((s) => upsertSession(s.id, {
    studentName: s.student_name, candidateIdentity: s.candidate_number || s.candidate_email, sessionState: s.session_state_current,
    riskScore: s.risk_score_current, status: s.status, authenticationMethod: s.authentication_method, clientType: s.client_type,
    extensionVersion: s.extension_version, browserName: s.browser_name, browserVersion: s.browser_version, platform: s.platform,
    lastSeenAt: s.last_seen_at, disconnectReason: s.disconnect_reason, integrityScore: s.integrity_score_current,
    integrityStatus: s.integrity_status_current, browserEventCount: s.browser_event_count, cameraStatus: s.camera_status,
    microphoneStatus: s.microphone_status, screenShareStatus: s.screen_share_status,
    resetCount: s.reset_count,
  }));
  initialLoadDone = true; renderAll();
}

async function loadExamPermissions() {
  const response = await API.request(`/exams/${encodeURIComponent(EXAM_ID)}`);
  if (!response.ok) return;
  const exam = await response.json();
  dashboardExam = exam;
  canEndSessions = (exam.allowed_actions || []).includes("exam.sessions.end");
  canResetSessions = (exam.allowed_actions || []).includes("exam.manage");
  renderExamDetailHeader(exam);
  document.getElementById("detail-manage-tab").classList.toggle(
    "hidden",
    !(exam.allowed_actions || []).includes("exam.manage"),
  );
}

async function resetSession(id, studentName) {
  const reason = prompt(`Lý do cấp lại phiên cho ${studentName}:`, "Khôi phục sau lỗi thiết bị hoặc kết nối");
  if (!reason || reason.trim().length < 3) return;
  const response = await API.request(`/sessions/${encodeURIComponent(id)}/reset`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return showToast(body.detail || "Không cấp lại được phiên.", "error");
  upsertSession(id, { status: body.status, riskScore: 0, sessionState: "SESSION_NORMAL", integrityScore: 0, integrityStatus: "healthy", browserEventCount: 0, cameraStatus: body.camera_status, microphoneStatus: body.microphone_status, screenShareStatus: body.screen_share_status, resetCount: body.reset_count, lastSeenAt: body.last_seen_at, disconnectReason: null });
  showToast("Đã lưu dữ liệu giám sát của lần thử trước và cấp lại phiên.", "success");
}

async function loadIncidents() {
  const filter = document.getElementById("incident-status-filter").value;
  const suffix = filter ? `?review_status=${encodeURIComponent(filter)}` : "";
  const response = await API.request(`/exams/${encodeURIComponent(EXAM_ID)}/incidents${suffix}`);
  const tbody = document.querySelector("#incidents-table tbody");
  if (!response.ok) {
    incidentData = [];
    hidePagination("incident-pagination");
    return showTableMessage(tbody, response.status === 403 ? "Bạn không có quyền duyệt sự cố." : "Không tải được hàng đợi sự cố.", 6);
  }
  incidentData = await response.json();
  renderIncidents();
}

function renderIncidents() {
  const tbody = document.querySelector("#incidents-table tbody");
  if (!incidentData.length) {
    hidePagination("incident-pagination");
    return showTableMessage(tbody, "Không có sự cố phù hợp.", 6);
  }
  const pageData = paginateItems(incidentData, incidentPage);
  incidentPage = pageData.page;
  tbody.replaceChildren(...pageData.items.map((item) => {
    const row = document.createElement("tr"); appendTextCell(row, item.student_name);
    const severity = document.createElement("td"); const badge = document.createElement("span"); badge.className = `badge badge-${String(item.severity).toLowerCase()}`; badge.textContent = SEVERITY_LABELS[item.severity] || item.severity; severity.appendChild(badge); row.appendChild(severity);
    appendTextCell(row, VIOLATION_LABELS[item.primary_violation] || item.primary_violation); appendTextCell(row, ({ new: "Mới", in_review: "Đang xem xét", confirmed: "Đã xác nhận", dismissed: "Đã bỏ qua" })[item.status] || item.status);
    appendTextCell(row, item.reviewed_by_email || "-");
    const action = document.createElement("td"); action.className = "table-actions";
    const actionGroup = document.createElement("div"); actionGroup.className = "table-actions-inner";
    const link = document.createElement("a"); link.href = `/ui/exams/${encodeURIComponent(EXAM_ID)}/sessions/${encodeURIComponent(item.session_id)}`; link.textContent = "Xem và duyệt";
    actionGroup.appendChild(link); action.appendChild(actionGroup); row.appendChild(action); return row;
  }));
  renderPagination("incident-pagination", pageData, incidentData.length, (nextPage) => {
    incidentPage = nextPage;
    renderIncidents();
  });
}

function openEndDialog(id, studentName) { endingSessionId = id; document.getElementById("end-session-student").textContent = studentName; document.getElementById("end-session-dialog").showModal(); }
function closeEndDialog() { endingSessionId = null; document.getElementById("end-session-dialog").close(); }

async function submitEndSession(event) {
  event.preventDefault(); if (!endingSessionId) return;
  const reason = document.getElementById("end-session-reason").value.trim(); if (reason.length < 3) return;
  const response = await API.request(`/sessions/${encodeURIComponent(endingSessionId)}/end`, { method: "POST", body: JSON.stringify({ reason }) });
  if (!response.ok) return showToast("Không thể kết thúc phiên.", "error");
  const ended = await response.json(); upsertSession(ended.id, { status: ended.status, disconnectReason: ended.disconnect_reason }); closeEndDialog(); showToast("Đã kết thúc phiên và ngắt kết nối ứng dụng giám sát.", "success");
}

function setWsStatus(text, error) { const el = document.getElementById("ws-status"); el.textContent = text; el.className = error ? "error" : "muted"; }
function connectDashboardWs() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws/dashboard/${encodeURIComponent(EXAM_ID)}`);
  ws.onopen = () => setWsStatus("Đang nhận cập nhật trực tiếp.", false);
  ws.onmessage = (event) => {
    let msg; try { msg = JSON.parse(event.data); } catch { return; }
    if (msg.type === "risk_update") upsertSession(msg.session_id, { studentName: msg.student_name, sessionState: msg.data.session_state, riskScore: msg.data.risk_score, status: "active", lastSeenAt: msg.server_received_at });
    else if (msg.type === "session_ended") upsertSession(msg.session_id, { status: "ended", disconnectReason: msg.data?.reason });
    else if (msg.type === "session_disconnected") upsertSession(msg.session_id, { status: "disconnected", disconnectReason: msg.data?.reason });
    else if (msg.type === "session_reset") upsertSession(msg.session_id, { status: "pending", riskScore: 0, sessionState: "SESSION_NORMAL", integrityScore: 0, integrityStatus: "healthy", browserEventCount: 0, resetCount: msg.data?.reset_count });
    else if (msg.type === "browser_event") { upsertSession(msg.session_id, { studentName: msg.student_name, status: "active", lastSeenAt: msg.server_received_at, integrityScore: msg.data.integrity_score, integrityStatus: msg.data.integrity_status, browserEventCount: msg.data.browser_event_count, cameraStatus: msg.data.camera_status, microphoneStatus: msg.data.microphone_status, screenShareStatus: msg.data.screen_share_status }); loadIncidents().catch(() => {}); }
  };
  ws.onclose = (event) => { if ([4401, 4403].includes(event.code)) return location.replace("/ui/login"); setWsStatus("Mất kết nối máy chủ – đang kết nối lại...", true); clearTimeout(reconnectTimer); reconnectTimer = setTimeout(connectDashboardWs, 3000); };
}

async function initializeDashboard() {
  const user = await API.requireAuth(); if (!user) return;
  if (user.is_system_admin) { const back = document.getElementById("dashboard-back-link"); back.href = "/ui/system/evidence"; back.textContent = "← Dữ liệu được cấp quyền"; }
  try {
    await loadExamPermissions(); await loadInitialSessions(); await loadIncidents(); connectDashboardWs();
    refreshTimer = setInterval(() => { loadInitialSessions().catch(() => {}); loadIncidents().catch(() => {}); }, 30000);
  } catch (error) { initialLoadDone = true; renderAll(); showToast(error.message || "Không tải được bảng giám sát.", "error"); }
}

["session-search", "session-status-filter", "session-sort"].forEach((id) => document.getElementById(id).addEventListener("input", () => {
  sessionPage = 1;
  renderTable();
}));
document.getElementById("incident-status-filter").addEventListener("change", () => {
  incidentPage = 1;
  loadIncidents().catch(() => {});
});
document.getElementById("end-session-form").addEventListener("submit", submitEndSession);
document.getElementById("end-session-close").addEventListener("click", closeEndDialog);
document.getElementById("end-session-cancel").addEventListener("click", closeEndDialog);
document.getElementById("detail-close-exam").addEventListener("click", () => {
  closeDashboardExam().catch((error) => showToast(error.message, "error"));
});
document.getElementById("detail-join-code").addEventListener("click", () => {
  copyDashboardJoinCode().catch((error) => showToast(error.message, "error"));
});
initializeDashboard();
