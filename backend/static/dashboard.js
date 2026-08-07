const dashboardRoot = document.getElementById("dashboard-root");
const EXAM_ID = dashboardRoot.dataset.examId;
const sessionData = new Map();
let initialLoadDone = false;
let lastUpdatedId = null;
let reconnectTimer = null;
let refreshTimer = null;

function stateBadgeInfo(status, sessionState) {
  if (status === "ended") return { cls: "badge-ended", label: "KẾT THÚC" };
  if (status === "disconnected") return { cls: "badge-medium", label: "MẤT KẾT NỐI" };
  if (status === "pending") return { cls: "badge-medium", label: "CHỜ CLIENT" };
  if (sessionState === "SESSION_ALERT") return { cls: "badge-high", label: "SESSION_ALERT" };
  return { cls: "badge-low", label: "SESSION_NORMAL" };
}

function appendTextCell(row, text) {
  const cell = document.createElement("td");
  cell.textContent = String(text);
  row.appendChild(cell);
  return cell;
}

function showTableMessage(tbody, message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 7;
  cell.className = "muted";
  cell.textContent = message;
  row.appendChild(cell);
  tbody.replaceChildren(row);
}

function renderKpis() {
  const all = [...sessionData.values()];
  const active = all.filter((session) => session.status === "active");
  const alerting = active.filter((session) => session.sessionState === "SESSION_ALERT").length;
  const avgRisk = active.length
    ? active.reduce((sum, session) => sum + session.riskScore, 0) / active.length
    : 0;
  const ended = all.filter((session) => session.status === "ended").length;
  const integrityAlerts = active.filter((session) => session.integrityStatus === "alert").length;

  const tiles = [
    { label: "Đang tham gia", value: active.length, alert: false },
    { label: "Đang cảnh báo", value: alerting, alert: alerting > 0 },
    { label: "Điểm rủi ro TB", value: avgRisk.toFixed(1), alert: false },
    { label: "Cảnh báo trình duyệt", value: integrityAlerts, alert: integrityAlerts > 0 },
    { label: "Đã kết thúc", value: ended, alert: false },
  ];

  const elements = tiles.map((tile) => {
    const wrapper = document.createElement("div");
    wrapper.className = `kpi-tile${tile.alert ? " kpi-alert" : ""}`;
    const value = document.createElement("div");
    value.className = "kpi-value";
    value.textContent = String(tile.value);
    const label = document.createElement("div");
    label.className = "kpi-label";
    label.textContent = tile.label;
    wrapper.append(value, label);
    return wrapper;
  });
  document.getElementById("kpi-row").replaceChildren(...elements);
}

function renderTable() {
  const tbody = document.querySelector("#sessions-table tbody");
  if (!initialLoadDone) {
    showTableMessage(tbody, "Đang tải...");
    return;
  }
  if (sessionData.size === 0) {
    showTableMessage(tbody, "Chưa có thí sinh nào tham gia kỳ thi này.");
    return;
  }

  const rows = [...sessionData.entries()].map(([id, session]) => {
    const badgeInfo = stateBadgeInfo(session.status, session.sessionState);
    const row = document.createElement("tr");
    if (id === lastUpdatedId) row.classList.add("updated");
    appendTextCell(row, session.studentName);
    appendTextCell(row, session.candidateIdentity || "-");
    appendTextCell(
      row,
      `${session.authenticationMethod === "google" ? "Google" : "Thủ công"} · ${session.clientType === "browser_extension" ? `Extension ${session.extensionVersion || ""}` : "Desktop CV"}`,
    );

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${badgeInfo.cls}`;
    badge.textContent = badgeInfo.label;
    statusCell.appendChild(badge);
    row.appendChild(statusCell);
    appendTextCell(row, session.riskScore.toFixed(1));

    const integrityCell = document.createElement("td");
    const integrityBadge = document.createElement("span");
    const integrityClass = session.integrityStatus === "alert"
      ? "badge-high"
      : session.integrityStatus === "warning" ? "badge-medium" : "badge-low";
    integrityBadge.className = `badge ${integrityClass}`;
    integrityBadge.textContent = `${session.integrityStatus.toUpperCase()} · ${session.browserEventCount}`;
    integrityCell.appendChild(integrityBadge);
    row.appendChild(integrityCell);

    const detailCell = document.createElement("td");
    const link = document.createElement("a");
    link.href = `/ui/exams/${encodeURIComponent(EXAM_ID)}/sessions/${encodeURIComponent(id)}`;
    link.textContent = "Xem chi tiết";
    detailCell.appendChild(link);
    row.appendChild(detailCell);
    return row;
  });
  tbody.replaceChildren(...rows);
}

function renderAll() {
  renderKpis();
  renderTable();
}

function safeRiskScore(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function upsertSession(id, studentName, sessionState, riskScore, status, extra = {}) {
  const existing = sessionData.get(id) || {};
  sessionData.set(id, {
    studentName: studentName ?? existing.studentName ?? "-",
    sessionState: sessionState ?? existing.sessionState ?? "SESSION_NORMAL",
    riskScore: safeRiskScore(riskScore, existing.riskScore ?? 0),
    status: status ?? existing.status ?? "active",
    candidateIdentity: extra.candidateIdentity ?? existing.candidateIdentity ?? null,
    authenticationMethod: extra.authenticationMethod ?? existing.authenticationMethod ?? "manual",
    clientType: extra.clientType ?? existing.clientType ?? "desktop_cv",
    extensionVersion: extra.extensionVersion ?? existing.extensionVersion ?? null,
    integrityScore: safeRiskScore(extra.integrityScore, existing.integrityScore ?? 0),
    integrityStatus: extra.integrityStatus ?? existing.integrityStatus ?? "healthy",
    browserEventCount: Number.isFinite(Number(extra.browserEventCount))
      ? Number(extra.browserEventCount)
      : existing.browserEventCount ?? 0,
  });
  lastUpdatedId = id;
  renderAll();
}

function markStatus(id, status) {
  const existing = sessionData.get(id);
  if (!existing) return;
  existing.status = status;
  lastUpdatedId = id;
  renderAll();
}

async function loadInitialSessions() {
  const response = await API.request(`/exams/${encodeURIComponent(EXAM_ID)}/sessions`);
  if (!response.ok) throw new Error("Không tải được danh sách phiên.");
  const sessions = await response.json();
  sessions.forEach((session) => {
    sessionData.set(session.id, {
      studentName: session.student_name,
      sessionState: session.session_state_current,
      riskScore: safeRiskScore(session.risk_score_current),
      status: session.status,
      candidateIdentity: session.candidate_number || session.candidate_email,
      authenticationMethod: session.authentication_method,
      clientType: session.client_type,
      extensionVersion: session.extension_version,
      integrityScore: safeRiskScore(session.integrity_score_current),
      integrityStatus: session.integrity_status_current,
      browserEventCount: Number(session.browser_event_count) || 0,
    });
  });
  initialLoadDone = true;
  renderAll();
}

function setWsStatus(text, isError) {
  const element = document.getElementById("ws-status");
  if (!element) return;
  element.textContent = text;
  element.className = isError ? "error" : "muted";
}

function connectDashboardWs() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${window.location.host}/ws/dashboard/${encodeURIComponent(EXAM_ID)}`;
  const ws = new WebSocket(url);

  ws.onopen = () => setWsStatus("", false);
  ws.onmessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (error) {
      return;
    }
    if (message.type === "risk_update") {
      upsertSession(
        message.session_id,
        message.student_name,
        message.data.session_state,
        message.data.risk_score,
        "active",
      );
    } else if (message.type === "session_ended") {
      markStatus(message.session_id, "ended");
    } else if (message.type === "session_disconnected") {
      markStatus(message.session_id, "disconnected");
    } else if (message.type === "browser_event") {
      upsertSession(
        message.session_id,
        message.student_name,
        null,
        null,
        "active",
        {
          integrityScore: message.data.integrity_score,
          integrityStatus: message.data.integrity_status,
          browserEventCount: message.data.browser_event_count,
        },
      );
    }
  };
  ws.onclose = (event) => {
    if (event.code === 4401 || event.code === 4403) {
      window.location.replace("/ui/login");
      return;
    }
    setWsStatus("Mất kết nối với backend - đang thử kết nối lại...", true);
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectDashboardWs, 3000);
  };
}

async function initializeDashboard() {
  const user = await API.requireAuth();
  if (!user) return;
  if (user.is_system_admin) {
    const backLink = document.getElementById("dashboard-back-link");
    backLink.href = "/ui/system/evidence";
    backLink.textContent = "← Dữ liệu break-glass";
  }
  try {
    await loadInitialSessions();
    connectDashboardWs();
    clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
      loadInitialSessions().catch(() => {});
    }, 30_000);
  } catch (error) {
    initialLoadDone = true;
    renderAll();
    showToast(error.message || "Không tải được dashboard.", "error");
  }
}

initializeDashboard();
