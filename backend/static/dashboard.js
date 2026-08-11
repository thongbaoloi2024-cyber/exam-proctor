const dashboardRoot = document.getElementById("dashboard-root");
const EXAM_ID = dashboardRoot.dataset.examId;
const sessionData = new Map();
let initialLoadDone = false;
let lastUpdatedId = null;
let reconnectTimer = null;
let refreshTimer = null;
let canEndSessions = false;
let canResetSessions = false;
let endingSessionId = null;

function stateBadgeInfo(status, sessionState) {
  if (status === "ended") return { cls: "badge-ended", label: "KẾT THÚC" };
  if (status === "disconnected") return { cls: "badge-medium", label: "MẤT KẾT NỐI" };
  if (status === "pending") return { cls: "badge-medium", label: "CHỜ CLIENT" };
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
    ["Risk trung bình", avgRisk.toFixed(1), false],
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
  if (!value) return "Chưa có heartbeat";
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s trước`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} phút trước`;
  return new Date(value).toLocaleString("vi-VN");
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
  if (!initialLoadDone) return showTableMessage(tbody, "Đang tải...");
  const items = filteredSessions();
  if (!items.length) return showTableMessage(tbody, sessionData.size ? "Không có phiên phù hợp bộ lọc." : "Chưa có thí sinh nào tham gia kỳ thi này.");
  const rows = items.map(([id, session]) => {
    const row = document.createElement("tr");
    if (id === lastUpdatedId) row.classList.add("updated");
    appendTextCell(row, session.studentName);
    appendTextCell(row, session.candidateIdentity || "-");
    const client = session.clientType === "browser_extension"
      ? `${session.browserName || "Browser"} ${session.browserVersion || ""} · Ext ${session.extensionVersion || "-"}`
      : "Desktop CV";
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
    integrityBadge.textContent = `${session.integrityStatus.toUpperCase()} · ${session.browserEventCount}`;
    const devices = document.createElement("small"); devices.className = "muted device-status-line";
    devices.textContent = [statusText(session.cameraStatus, "Cam"), statusText(session.microphoneStatus, "Mic"), statusText(session.screenShareStatus, "Màn")].join(" · ");
    integrityCell.append(integrityBadge, devices); row.appendChild(integrityCell);
    const actions = document.createElement("td"); actions.className = "table-actions";
    const detail = document.createElement("a"); detail.href = `/ui/exams/${encodeURIComponent(EXAM_ID)}/sessions/${encodeURIComponent(id)}`; detail.textContent = "Chi tiết";
    actions.appendChild(detail);
    if (canEndSessions && session.status !== "ended") {
      const end = document.createElement("button"); end.type = "button"; end.className = "link-button danger-text"; end.textContent = "Kết thúc";
      end.addEventListener("click", () => openEndDialog(id, session.studentName)); actions.appendChild(end);
    }
    if (canResetSessions && ["ended", "disconnected"].includes(session.status)) {
      const reset = document.createElement("button"); reset.type = "button"; reset.className = "link-button"; reset.textContent = "Reset phiên";
      reset.addEventListener("click", () => resetSession(id, session.studentName)); actions.appendChild(reset);
    }
    row.appendChild(actions); return row;
  });
  tbody.replaceChildren(...rows);
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
  canEndSessions = (exam.allowed_actions || []).includes("exam.sessions.end");
  canResetSessions = (exam.allowed_actions || []).includes("exam.manage");
}

async function resetSession(id, studentName) {
  const reason = prompt(`Lý do reset phiên của ${studentName}:`, "Khôi phục sau lỗi thiết bị/kết nối");
  if (!reason || reason.trim().length < 3) return;
  const response = await API.request(`/sessions/${encodeURIComponent(id)}/reset`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return showToast(body.detail || "Không reset được phiên.", "error");
  upsertSession(id, { status: body.status, riskScore: 0, sessionState: "SESSION_NORMAL", integrityScore: 0, integrityStatus: "healthy", browserEventCount: 0, cameraStatus: body.camera_status, microphoneStatus: body.microphone_status, screenShareStatus: body.screen_share_status, resetCount: body.reset_count, lastSeenAt: body.last_seen_at, disconnectReason: null });
  showToast("Đã lưu evidence attempt cũ và cấp lại phiên.", "success");
}

async function loadIncidents() {
  const filter = document.getElementById("incident-status-filter").value;
  const suffix = filter ? `?review_status=${encodeURIComponent(filter)}` : "";
  const response = await API.request(`/exams/${encodeURIComponent(EXAM_ID)}/incidents${suffix}`);
  const tbody = document.querySelector("#incidents-table tbody");
  if (!response.ok) return showTableMessage(tbody, response.status === 403 ? "Bạn không có quyền duyệt sự cố." : "Không tải được hàng đợi sự cố.", 6);
  const incidents = await response.json();
  if (!incidents.length) return showTableMessage(tbody, "Không có sự cố phù hợp.", 6);
  tbody.replaceChildren(...incidents.map((item) => {
    const row = document.createElement("tr"); appendTextCell(row, item.student_name);
    const severity = document.createElement("td"); const badge = document.createElement("span"); badge.className = `badge badge-${String(item.severity).toLowerCase()}`; badge.textContent = item.severity; severity.appendChild(badge); row.appendChild(severity);
    appendTextCell(row, item.primary_violation); appendTextCell(row, ({ new: "Mới", in_review: "Đang duyệt", confirmed: "Đã xác nhận", dismissed: "Đã bỏ qua" })[item.status] || item.status);
    appendTextCell(row, item.reviewed_by_email || "-");
    const action = document.createElement("td"); const link = document.createElement("a"); link.href = `/ui/exams/${encodeURIComponent(EXAM_ID)}/sessions/${encodeURIComponent(item.session_id)}`; link.textContent = "Xem và duyệt"; action.appendChild(link); row.appendChild(action); return row;
  }));
}

function openEndDialog(id, studentName) { endingSessionId = id; document.getElementById("end-session-student").textContent = studentName; document.getElementById("end-session-dialog").showModal(); }
function closeEndDialog() { endingSessionId = null; document.getElementById("end-session-dialog").close(); }

async function submitEndSession(event) {
  event.preventDefault(); if (!endingSessionId) return;
  const reason = document.getElementById("end-session-reason").value.trim(); if (reason.length < 3) return;
  const response = await API.request(`/sessions/${encodeURIComponent(endingSessionId)}/end`, { method: "POST", body: JSON.stringify({ reason }) });
  if (!response.ok) return showToast("Không thể kết thúc phiên.", "error");
  const ended = await response.json(); upsertSession(ended.id, { status: ended.status, disconnectReason: ended.disconnect_reason }); closeEndDialog(); showToast("Đã kết thúc phiên và ngắt client.", "success");
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
  ws.onclose = (event) => { if ([4401, 4403].includes(event.code)) return location.replace("/ui/login"); setWsStatus("Mất kết nối backend - đang kết nối lại...", true); clearTimeout(reconnectTimer); reconnectTimer = setTimeout(connectDashboardWs, 3000); };
}

async function initializeDashboard() {
  const user = await API.requireAuth(); if (!user) return;
  if (user.is_system_admin) { const back = document.getElementById("dashboard-back-link"); back.href = "/ui/system/evidence"; back.textContent = "← Dữ liệu break-glass"; }
  try {
    await loadExamPermissions(); await loadInitialSessions(); await loadIncidents(); connectDashboardWs();
    refreshTimer = setInterval(() => { loadInitialSessions().catch(() => {}); loadIncidents().catch(() => {}); }, 30000);
  } catch (error) { initialLoadDone = true; renderAll(); showToast(error.message || "Không tải được dashboard.", "error"); }
}

["session-search", "session-status-filter", "session-sort"].forEach((id) => document.getElementById(id).addEventListener("input", renderTable));
document.getElementById("incident-status-filter").addEventListener("change", () => loadIncidents().catch(() => {}));
document.getElementById("end-session-form").addEventListener("submit", submitEndSession);
document.getElementById("end-session-close").addEventListener("click", closeEndDialog);
document.getElementById("end-session-cancel").addEventListener("click", closeEndDialog);
initializeDashboard();
