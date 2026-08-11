const detailRoot = document.getElementById("session-detail-root");
const EXAM_ID = detailRoot.dataset.examId;
const SESSION_ID = detailRoot.dataset.sessionId;
const SEVERITY_BADGE_CLASS = { LOW: "badge-low", MEDIUM: "badge-medium", HIGH: "badge-high" };
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
const SESSION_STATUS_LABELS = { pending: "Chờ kết nối", active: "Đang tham gia", disconnected: "Mất kết nối", ended: "Đã kết thúc" };
const AUTHENTICATION_LABELS = { google: "Tài khoản Google", manual: "Họ tên và mã thí sinh" };
const CLIENT_LABELS = { browser_extension: "Tiện ích trình duyệt", desktop_cv: "Ứng dụng giám sát máy tính" };
const DEVICE_STATUS_LABELS = { ready: "sẵn sàng", issue: "có lỗi", pending: "đang chờ", unknown: "chưa rõ", not_required: "không yêu cầu" };
const snapshotObjectUrls = [];
const incidentReviews = new Map();
const BROWSER_EVENT_LABELS = {
  MEDIA_READY: "Camera, micrô và chia sẻ màn hình sẵn sàng",
  CONTENT_MONITOR_READY: "Bộ giám sát trang sẵn sàng",
  TAB_HIDDEN: "Ẩn tab bài thi",
  TAB_VISIBLE: "Quay lại tab bài thi",
  WINDOW_BLUR: "Rời cửa sổ bài thi",
  WINDOW_FOCUS: "Quay lại cửa sổ bài thi",
  TAB_SWITCHED: "Chuyển tab",
  NEW_TAB: "Mở tab mới",
  NAVIGATION_AWAY: "Điều hướng khỏi miền bài thi",
  FULLSCREEN_EXIT: "Thoát toàn màn hình",
  FULLSCREEN_ENTER: "Vào toàn màn hình",
  CLIPBOARD_COPY: "Sao chép hoặc cắt nội dung",
  CLIPBOARD_PASTE: "Dán nội dung",
  CONTEXT_MENU: "Mở trình đơn chuột phải",
  CAMERA_MUTED: "Camera tạm dừng",
  CAMERA_ENDED: "Camera dừng",
  MICROPHONE_MUTED: "Micrô tạm dừng",
  MICROPHONE_ENDED: "Micrô dừng",
  SCREEN_SHARE_ENDED: "Chia sẻ màn hình dừng",
  MONITOR_CLOSED: "Cửa sổ giám sát đóng",
  PERMISSION_MISSING: "Thiếu quyền bắt buộc",
};
const reportPollTimers = new Map();
let unifiedTimeline = [];
let violationData = [];
let browserEventData = [];
const severityOrder = { LOW: 1, MEDIUM: 2, HIGH: 3 };
const unifiedTableState = TableUI.createState({ pageSize: 10, sortKey: "time" });
const violationTableState = TableUI.createState({ pageSize: 10, sortKey: "time" });
const browserEventTableState = TableUI.createState({ pageSize: 10, sortKey: "time" });
const UNIFIED_SORT_COLUMNS = {
  time: { value: (item) => numeric(item.time), type: "number" },
  source: (item) => item.source,
  severity: { value: (item) => severityOrder[item.severity] || 0, type: "number" },
  type: (item) => item.type,
  detail: (item) => item.detail,
};
const VIOLATION_SORT_COLUMNS = {
  time: { value: (item) => numeric(item.video_time_sec), type: "number" },
  severity: { value: (item) => severityOrder[String(item.severity || "LOW")] || 0, type: "number" },
  type: (item) => VIOLATION_LABELS[item.primary_violation] || item.primary_violation,
};
const BROWSER_SORT_COLUMNS = {
  time: { value: (item) => numeric(item.video_time_sec), type: "number" },
  severity: { value: (item) => severityOrder[String(item.severity || "LOW")] || 0, type: "number" },
  type: (item) => BROWSER_EVENT_LABELS[item.event_type] || item.event_type,
  detail: (item) => item.observed_origin || item.server_duration_ms,
};

function numeric(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function showTableMessage(tbody, message, columns = 4) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.className = "muted";
  cell.textContent = message;
  row.appendChild(cell);
  tbody.replaceChildren(row);
}

function appendBrowserEventRow(tbody, browserEvent) {
  const row = document.createElement("tr");
  const timeCell = document.createElement("td");
  timeCell.textContent = numeric(browserEvent.video_time_sec).toFixed(1);

  const severityCell = document.createElement("td");
  const badge = document.createElement("span");
  const severity = String(browserEvent.severity || "LOW");
  badge.className = `badge ${SEVERITY_BADGE_CLASS[severity] || "badge-low"}`;
  badge.textContent = SEVERITY_LABELS[severity] || severity;
  severityCell.appendChild(badge);

  const eventCell = document.createElement("td");
  eventCell.textContent = BROWSER_EVENT_LABELS[browserEvent.event_type] || String(browserEvent.event_type || "-");
  const detailCell = document.createElement("td");
  const details = [];
  if (browserEvent.server_duration_ms != null) details.push(`${(numeric(browserEvent.server_duration_ms) / 1000).toFixed(1)}s`);
  if (browserEvent.observed_origin) details.push(String(browserEvent.observed_origin));
  detailCell.textContent = details.join(" · ") || "-";

  const snapshotCell = document.createElement("td");
  if (browserEvent.snapshot_path) {
    const filename = String(browserEvent.snapshot_path).split(/[\\/]/).pop();
    const img = document.createElement("img");
    img.className = "snapshot-thumb";
    img.alt = "Ảnh bằng chứng trình duyệt";
    snapshotCell.appendChild(img);
    loadSnapshot(
      img,
      `/sessions/${encodeURIComponent(SESSION_ID)}/snapshots/${encodeURIComponent(filename)}`,
    ).catch(() => {});
  } else {
    snapshotCell.textContent = "-";
  }
  row.append(timeCell, severityCell, eventCell, detailCell, snapshotCell);
  tbody.appendChild(row);
}

function renderRiskChart(riskTimeline) {
  const svg = document.getElementById("risk-chart");
  const startLabel = document.getElementById("chart-time-start");
  const endLabel = document.getElementById("chart-time-end");
  const maxLabel = document.getElementById("chart-score-max");

  if (!Array.isArray(riskTimeline) || riskTimeline.length === 0) {
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = "Chưa có dữ liệu điểm rủi ro cho phiên này.";
    svg.parentElement.replaceChildren(note);
    return;
  }

  const pointsData = riskTimeline.map((point) => ({
    time: Math.max(0, numeric(point.video_time_sec)),
    score: Math.max(0, numeric(point.risk_score)),
  }));
  const width = 600;
  const height = 150;
  const padding = 8;
  const maxTime = Math.max(...pointsData.map((point) => point.time), 1);
  const maxScore = Math.max(...pointsData.map((point) => point.score), 1);
  const points = pointsData.map((point) => {
    const x = padding + (point.time / maxTime) * (width - 2 * padding);
    const y = height - padding - (point.score / maxScore) * (height - 2 * padding);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  polyline.setAttribute("points", points);
  polyline.setAttribute("fill", "none");
  polyline.setAttribute("stroke", "#4f8ef7");
  polyline.setAttribute("stroke-width", "2");
  svg.replaceChildren(polyline);
  startLabel.textContent = "0s";
  endLabel.textContent = `${maxTime.toFixed(0)}s`;
  maxLabel.textContent = `Điểm rủi ro cao nhất: ${maxScore.toFixed(1)}`;
}

function renderUnifiedTimeline() {
  const filter = document.getElementById("timeline-severity-filter").value;
  const items = unifiedTimeline.filter((item) => !filter || item.severity === filter);
  const tbody = document.querySelector("#unified-timeline-table tbody");
  if (!items.length) {
    TableUI.hidePagination("unified-timeline-pagination");
    return showTableMessage(tbody, "Không có sự kiện phù hợp.", 5);
  }
  const sorted = TableUI.sortItems(items, unifiedTableState, UNIFIED_SORT_COLUMNS);
  const pageData = TableUI.paginate(sorted, unifiedTableState);
  tbody.replaceChildren(...pageData.items.map((item) => {
    const row = document.createElement("tr");
    [numeric(item.time).toFixed(1), item.source].forEach((value) => { const cell = document.createElement("td"); cell.textContent = value; row.appendChild(cell); });
    const severityCell = document.createElement("td"); const badge = document.createElement("span"); badge.className = `badge ${SEVERITY_BADGE_CLASS[item.severity] || "badge-low"}`; badge.textContent = SEVERITY_LABELS[item.severity] || item.severity; severityCell.appendChild(badge); row.appendChild(severityCell);
    [item.type, item.detail || "-"].forEach((value) => { const cell = document.createElement("td"); cell.textContent = value; row.appendChild(cell); });
    return row;
  }));
  TableUI.renderPagination("unified-timeline-pagination", pageData, (nextPage) => {
    unifiedTableState.page = nextPage;
    renderUnifiedTimeline();
  });
}

async function loadSnapshot(img, url) {
  const response = await API.request(url);
  if (!response.ok) return;
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  snapshotObjectUrls.push(objectUrl);
  img.src = objectUrl;
  img.addEventListener("click", () => window.open(objectUrl, "_blank", "noopener"));
}

async function saveIncidentReview(eventId, status, note) {
  const response = await API.request(
    `/sessions/${encodeURIComponent(SESSION_ID)}/incidents/${encodeURIComponent(eventId)}`,
    { method: "PUT", body: JSON.stringify({ status, note: note || null }) },
  );
  if (!response.ok) {
    showToast("Không lưu được kết luận sự cố.", "error");
    return;
  }
  incidentReviews.set(eventId, await response.json());
  showToast("Đã lưu kết luận sự cố.", "success");
}

function appendViolationRow(tbody, violation) {
  const row = document.createElement("tr");
  const timeCell = document.createElement("td");
  timeCell.textContent = numeric(violation.video_time_sec).toFixed(1);

  const severityCell = document.createElement("td");
  const badge = document.createElement("span");
  const severity = String(violation.severity || "LOW");
  badge.className = `badge ${SEVERITY_BADGE_CLASS[severity] || "badge-low"}`;
  badge.textContent = SEVERITY_LABELS[severity] || severity;
  severityCell.appendChild(badge);

  const typeCell = document.createElement("td");
  typeCell.textContent = VIOLATION_LABELS[violation.primary_violation] || String(violation.primary_violation || "-");
  const snapshotCell = document.createElement("td");

  if (violation.snapshot_path) {
    const filename = String(violation.snapshot_path).split(/[\\/]/).pop();
    const img = document.createElement("img");
    img.className = "snapshot-thumb";
    img.alt = "Ảnh chụp bằng chứng";
    img.title = "Nhấn để xem ảnh đầy đủ";
    snapshotCell.appendChild(img);
    const url = `/sessions/${encodeURIComponent(SESSION_ID)}/snapshots/${encodeURIComponent(filename)}`;
    loadSnapshot(img, url).catch(() => {});
  } else {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "-";
    snapshotCell.appendChild(empty);
  }

  const reviewCell = document.createElement("td");
  const eventId = String(violation.event_id || "");
  if (eventId) {
    const current = incidentReviews.get(eventId);
    const reviewStatus = document.createElement("select");
    reviewStatus.replaceChildren(...[
      ["new", "Mới"],
      ["in_review", "Đang xem xét"],
      ["confirmed", "Xác nhận"],
      ["dismissed", "Bỏ qua"],
    ].map(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      return option;
    }));
    reviewStatus.value = current?.status || "new";
    const note = document.createElement("input");
    note.placeholder = "Ghi chú";
    note.value = current?.note || "";
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "Lưu";
    save.addEventListener("click", () => saveIncidentReview(eventId, reviewStatus.value, note.value));
    reviewCell.append(reviewStatus, note, save);
  } else {
    reviewCell.textContent = "–";
  }

  row.append(timeCell, severityCell, typeCell, snapshotCell, reviewCell);
  tbody.appendChild(row);
}

async function loadIncidentReviews() {
  const response = await API.request(`/sessions/${encodeURIComponent(SESSION_ID)}/incidents`);
  if (!response.ok) return;
  const reviews = await response.json();
  reviews.forEach((review) => incidentReviews.set(review.violation_event_id, review));
}

function renderViolations() {
  const tbody = document.querySelector("#violations-table tbody");
  tbody.replaceChildren();
  if (!violationData.length) {
    TableUI.hidePagination("violations-pagination");
    return showTableMessage(tbody, "Không có vi phạm nào được ghi nhận.", 5);
  }
  const sorted = TableUI.sortItems(violationData, violationTableState, VIOLATION_SORT_COLUMNS);
  const pageData = TableUI.paginate(sorted, violationTableState);
  pageData.items.forEach((violation) => appendViolationRow(tbody, violation));
  TableUI.renderPagination("violations-pagination", pageData, (nextPage) => {
    violationTableState.page = nextPage;
    renderViolations();
  });
}

function renderBrowserEvents() {
  const tbody = document.querySelector("#browser-events-table tbody");
  tbody.replaceChildren();
  if (!browserEventData.length) {
    TableUI.hidePagination("browser-events-pagination");
    return showTableMessage(tbody, "Không có sự kiện trình duyệt nào được ghi nhận.", 5);
  }
  const sorted = TableUI.sortItems(browserEventData, browserEventTableState, BROWSER_SORT_COLUMNS);
  const pageData = TableUI.paginate(sorted, browserEventTableState);
  pageData.items.forEach((browserEvent) => appendBrowserEventRow(tbody, browserEvent));
  TableUI.renderPagination("browser-events-pagination", pageData, (nextPage) => {
    browserEventTableState.page = nextPage;
    renderBrowserEvents();
  });
}

async function loadDetail() {
  const response = await API.request(`/sessions/${encodeURIComponent(SESSION_ID)}/detail`);
  if (!response.ok) throw new Error("Không tải được chi tiết phiên.");
  const detail = await response.json();

  document.getElementById("student-name-heading").textContent = `Chi tiết phiên - ${detail.student_name}`;
  const meta = detail.session_meta || {};
  const durationLabel = meta.duration_sec != null ? `${numeric(meta.duration_sec).toFixed(1)}s` : "đang diễn ra";
  const violations = Array.isArray(detail.violations) ? detail.violations : [];
  violationData = violations;
  document.getElementById("session-summary").textContent =
    `Trạng thái: ${SESSION_STATUS_LABELS[detail.status] || detail.status} · Xác thực: ${AUTHENTICATION_LABELS[detail.authentication_method] || detail.authentication_method} · Thiết bị: ${CLIENT_LABELS[detail.client_type] || detail.client_type}`
    + ` · Thời lượng: ${durationLabel} · Vi phạm hình ảnh: ${violations.length}`
    + ` · Sự kiện trình duyệt: ${detail.browser_event_count}`
    + ` · Trạng thái thiết bị: Camera ${DEVICE_STATUS_LABELS[detail.camera_status] || detail.camera_status}, micrô ${DEVICE_STATUS_LABELS[detail.microphone_status] || detail.microphone_status}, màn hình ${DEVICE_STATUS_LABELS[detail.screen_share_status] || detail.screen_share_status}`
    + `${detail.disconnect_reason ? ` · Ngắt: ${detail.disconnect_reason}` : ""}`
    + `${detail.reset_count ? ` · Đã cấp lại ${detail.reset_count} lần` : ""}`;

  renderRiskChart(detail.risk_timeline);
  renderViolations();

  const browserEvents = Array.isArray(detail.browser_events) ? detail.browser_events : [];
  browserEventData = browserEvents;
  unifiedTimeline = [
    ...violations.map((item) => ({ time: item.video_time_sec, source: "Phân tích hình ảnh", severity: String(item.severity || "LOW"), type: VIOLATION_LABELS[item.primary_violation] || String(item.primary_violation || "-"), detail: item.risk_score != null ? `Điểm rủi ro ${numeric(item.risk_score).toFixed(1)}` : "" })),
    ...browserEvents.map((item) => ({ time: item.video_time_sec, source: "Trình duyệt", severity: String(item.severity || "LOW"), type: BROWSER_EVENT_LABELS[item.event_type] || String(item.event_type || "-"), detail: item.observed_origin || (item.server_duration_ms != null ? `${(numeric(item.server_duration_ms) / 1000).toFixed(1)}s` : "") })),
  ].sort((left, right) => left.time - right.time);
  renderUnifiedTimeline();
  renderBrowserEvents();
}

function setReportStatus(text, isError = false) {
  const element = document.getElementById("report-job-status");
  element.textContent = text;
  element.className = isError ? "error" : "muted";
}

async function pollReportJob(jobId, format) {
  const response = await API.request(`/report-jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    setReportStatus("Không đọc được trạng thái báo cáo.", true);
    return;
  }
  const job = await response.json();
  if (job.status === "completed") {
    setReportStatus(`Báo cáo ${format.toUpperCase()} đã sẵn sàng.`);
    openAuthenticatedFile(`/report-jobs/${encodeURIComponent(jobId)}/download`);
    return;
  }
  if (job.status === "failed") {
    setReportStatus(job.error_message || "Tạo báo cáo thất bại.", true);
    return;
  }
  setReportStatus(job.status === "processing" ? "Đang tạo báo cáo..." : "Báo cáo đang chờ xử lý...");
  const timer = window.setTimeout(() => pollReportJob(jobId, format).catch(() => {
    setReportStatus("Mất kết nối khi chờ báo cáo.", true);
  }), 2000);
  reportPollTimers.set(format, timer);
}

async function createReport(format) {
  const button = document.getElementById(`report-${format}-button`);
  button.disabled = true;
  setReportStatus(`Đang gửi yêu cầu ${format.toUpperCase()}...`);
  try {
    const response = await API.request(
      `/sessions/${encodeURIComponent(SESSION_ID)}/report-jobs/${encodeURIComponent(format)}`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error("Không tạo được yêu cầu báo cáo.");
    const job = await response.json();
    clearTimeout(reportPollTimers.get(format));
    await pollReportJob(job.id, format);
  } catch (error) {
    setReportStatus(error.message || "Không tạo được báo cáo.", true);
  } finally {
    button.disabled = false;
  }
}

document.getElementById("report-html-button").addEventListener("click", () => createReport("html"));
document.getElementById("report-pdf-button").addEventListener("click", () => createReport("pdf"));
document.getElementById("timeline-severity-filter").addEventListener("change", () => {
  unifiedTableState.page = 1;
  renderUnifiedTimeline();
});
window.addEventListener("unload", () => {
  snapshotObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  reportPollTimers.forEach((timer) => clearTimeout(timer));
});

async function initializeDetail() {
  const user = await API.requireAuth();
  if (!user) return;
  try {
    await loadIncidentReviews();
    await loadDetail();
  } catch (error) {
    showToast(error.message || "Không tải được chi tiết phiên.", "error");
  }
}

TableUI.bindSort("unified-timeline-table", unifiedTableState, renderUnifiedTimeline);
TableUI.bindSort("violations-table", violationTableState, renderViolations);
TableUI.bindSort("browser-events-table", browserEventTableState, renderBrowserEvents);
initializeDetail();
