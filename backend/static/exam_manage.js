const manageRoot = document.getElementById("exam-manage-root");
const MANAGE_EXAM_ID = manageRoot?.dataset.examId || "";
let managedExam = null;
let canAssign = false;
let managePolicyFloor = null;

function manageCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value == null ? "–" : String(value);
  row.appendChild(cell);
  return cell;
}

function localInputValue(value) {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function manageExpiryText(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `Hết hạn ${date.toLocaleString("vi-VN")}`;
}

function formatManageHeaderDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "–";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function renderManageDetailHeader(exam) {
  const statusLabels = {
    draft: "Bản nháp",
    scheduled: "Đã lên lịch",
    open: "Đang mở",
    closed: "Đã đóng",
    archived: "Đã lưu trữ",
  };
  document.getElementById("detail-exam-title").textContent = exam.name;
  document.getElementById("detail-created-at").textContent = formatManageHeaderDate(exam.created_at);
  document.getElementById("detail-updated-at").textContent = formatManageHeaderDate(exam.updated_at);
  const status = document.getElementById("detail-status");
  status.className = `exam-status-badge status-${exam.status}`;
  status.textContent = statusLabels[exam.status] || exam.status;
  const joinCode = document.getElementById("detail-join-code");
  joinCode.textContent = exam.join_code || "Đã ẩn";
  joinCode.title = manageExpiryText(exam.join_code_expires_at);
  document.title = `${exam.name} · Giám Thị Số`;
}

async function setLifecycle(status) {
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, expected_version: managedExam.version }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    showToast(typeof body.detail === "string" ? body.detail : "Không đổi được trạng thái.", "error");
    return;
  }
  managedExam = body;
  renderManagedExam();
  await loadReadiness();
}

function isoFromManageInput(value) {
  return value ? new Date(value).toISOString() : null;
}

function manageConfigIsEditable() {
  return Boolean(managedExam?.allowed_actions?.includes("exam.manage"))
    && managedExam.status === "draft";
}

function syncManageAuthMode() {
  const google = document.getElementById("manage-auth-mode").value === "google";
  document.getElementById("manage-google-domain-wrap").classList.toggle("hidden", !google);
  const requireExtension = document.getElementById("manage-require-extension");
  if (google) requireExtension.checked = true;
  requireExtension.disabled = !manageConfigIsEditable()
    || google
    || Boolean(managePolicyFloor?.require_extension);
  document.getElementById("manage-exam-url").required = requireExtension.checked;
}

function applyManagePolicyConstraints() {
  if (!managePolicyFloor) return;
  [
    ["manage-require-extension", "require_extension"],
    ["manage-require-fullscreen", "require_fullscreen"],
    ["manage-require-camera", "require_camera"],
    ["manage-require-microphone", "require_microphone"],
    ["manage-require-screen-share", "require_screen_share"],
    ["manage-block-clipboard", "block_clipboard"],
  ].forEach(([elementId, policyField]) => {
    if (managePolicyFloor[policyField]) {
      document.getElementById(elementId).checked = true;
      document.getElementById(elementId).disabled = true;
    }
  });
  document.getElementById("manage-focus-loss").max = String(managePolicyFloor.max_focus_loss_seconds);
  syncManageAuthMode();
}

function renderManagedExam() {
  const allowedActions = new Set(managedExam.allowed_actions || []);
  const canManage = allowedActions.has("exam.manage");
  renderManageDetailHeader(managedExam);
  document.getElementById("manage-exam-name").value = managedExam.name;
  document.getElementById("manage-exam-url").value = managedExam.exam_url || "";
  document.getElementById("manage-auth-mode").value = managedExam.candidate_auth_mode;
  document.getElementById("manage-google-domain").value = managedExam.google_allowed_domain || "";
  document.getElementById("manage-exam-start").value = localInputValue(managedExam.scheduled_start_at);
  document.getElementById("manage-exam-end").value = localInputValue(managedExam.scheduled_end_at);
  document.getElementById("manage-extension-version").value = managedExam.min_extension_version;
  document.getElementById("manage-focus-loss").value = managedExam.max_focus_loss_seconds;
  document.getElementById("manage-require-extension").checked = managedExam.require_extension;
  document.getElementById("manage-require-fullscreen").checked = managedExam.require_fullscreen;
  document.getElementById("manage-require-camera").checked = managedExam.require_camera;
  document.getElementById("manage-require-microphone").checked = managedExam.require_microphone;
  document.getElementById("manage-require-screen-share").checked = managedExam.require_screen_share;
  document.getElementById("manage-block-clipboard").checked = managedExam.block_clipboard;
  document.getElementById("exam-config-form").querySelectorAll("input,select,button").forEach((element) => {
    element.disabled = !canManage || managedExam.status !== "draft";
  });
  applyManagePolicyConstraints();
  const labels = { draft: "Về bản nháp", scheduled: "Lên lịch", open: "Mở", closed: "Đóng", archived: "Lưu trữ" };
  const buttons = (managedExam.allowed_transitions || []).map((status) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = labels[status];
    button.addEventListener("click", () => setLifecycle(status));
    return button;
  });
  document.getElementById("lifecycle-actions").replaceChildren(...buttons);
  document.getElementById("manage-rotate-code").classList.toggle(
    "hidden",
    !canManage || managedExam.status === "archived",
  );
}

async function rotateManagedJoinCode() {
  const requestedHours = window.prompt("Thời hạn mã mới (giờ, từ 0.1 đến 168):", "24");
  if (requestedHours == null) return;
  const ttlMinutes = Math.round(Number(requestedHours) * 60);
  if (!Number.isFinite(ttlMinutes) || ttlMinutes < 5 || ttlMinutes > 10080) {
    showToast("Thời hạn mã phải từ 5 phút đến 7 ngày.", "error");
    return;
  }
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/rotate-code`, {
    method: "POST",
    body: JSON.stringify({ expected_version: managedExam.version, ttl_minutes: ttlMinutes }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    showToast(typeof body.detail === "string" ? body.detail : "Không tạo lại được mã tham gia.", "error");
    return;
  }
  managedExam = body;
  renderManagedExam();
  showToast("Đã tạo mã tham gia mới; mã cũ không còn hiệu lực.", "success");
}

async function loadManagePolicyFloor() {
  const response = await API.request("/exams/policy/defaults");
  if (!response.ok) return;
  managePolicyFloor = await response.json();
}

async function loadReadiness() {
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/readiness`);
  if (!response.ok) return;
  const readiness = await response.json();
  document.getElementById("readiness-summary").textContent = readiness.ready
    ? "Tất cả kiểm tra đều đạt."
    : "Còn hạng mục cần xử lý trước khi mở kỳ thi.";
  const items = readiness.items.map((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = `readiness-item ${item.ready ? "ready" : "blocked"}`;
    const title = document.createElement("strong");
    title.textContent = `${item.ready ? "✓" : "!"} ${item.label}`;
    const detail = document.createElement("span");
    detail.className = "muted";
    detail.textContent = item.detail;
    wrapper.append(title, detail);
    return wrapper;
  });
  document.getElementById("readiness-list").replaceChildren(...items);
}

async function loadManagedExam() {
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}`);
  if (!response.ok) throw new Error("Không tải được kỳ thi.");
  managedExam = await response.json();
  renderManagedExam();
}

async function revokeAssignment(userId) {
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/assignments/${encodeURIComponent(userId)}`, { method: "DELETE" });
  if (!response.ok) {
    showToast("Không thu hồi được phân công.", "error");
    return;
  }
  await loadAssignments();
}

async function loadAssignments() {
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/assignments`);
  if (!response.ok) return;
  const assignments = await response.json();
  const rows = assignments.map((assignment) => {
    const row = document.createElement("tr");
    manageCell(row, assignment.email);
    manageCell(row, { owner: "Chủ kỳ thi", manager: "Quản lý", proctor: "Giám thị" }[assignment.assignment_role] || assignment.assignment_role);
    manageCell(row, assignment.status);
    manageCell(row, assignment.expires_at ? new Date(assignment.expires_at).toLocaleString("vi-VN") : "Không giới hạn");
    const actions = document.createElement("td");
    if (canAssign && assignment.assignment_role !== "owner" && assignment.status === "active") {
      const revoke = document.createElement("button");
      revoke.textContent = "Thu hồi";
      revoke.addEventListener("click", () => revokeAssignment(assignment.user_id));
      actions.appendChild(revoke);
    }
    row.appendChild(actions);
    return row;
  });
  document.querySelector("#assignments-table tbody").replaceChildren(...rows);
}

async function loadEligibleMembers() {
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/eligible-members`);
  canAssign = response.ok;
  document.getElementById("assignment-form").classList.toggle("hidden", !canAssign);
  if (!response.ok) return;
  const members = await response.json();
  const select = document.getElementById("assignment-user");
  select.replaceChildren(...members.map((member) => {
    const option = document.createElement("option");
    option.value = member.user_id;
    option.textContent = member.email;
    return option;
  }));
}

document.getElementById("exam-config-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}`, {
    method: "PATCH",
    body: JSON.stringify({
      expected_version: managedExam.version,
      name: document.getElementById("manage-exam-name").value,
      exam_url: document.getElementById("manage-exam-url").value || null,
      candidate_auth_mode: document.getElementById("manage-auth-mode").value,
      google_allowed_domain: document.getElementById("manage-auth-mode").value === "google"
        ? (document.getElementById("manage-google-domain").value.trim() || null)
        : null,
      scheduled_start_at: isoFromManageInput(document.getElementById("manage-exam-start").value),
      scheduled_end_at: isoFromManageInput(document.getElementById("manage-exam-end").value),
      min_extension_version: document.getElementById("manage-extension-version").value,
      max_focus_loss_seconds: Number(document.getElementById("manage-focus-loss").value),
      require_extension: document.getElementById("manage-require-extension").checked,
      require_fullscreen: document.getElementById("manage-require-fullscreen").checked,
      require_camera: document.getElementById("manage-require-camera").checked,
      require_microphone: document.getElementById("manage-require-microphone").checked,
      require_screen_share: document.getElementById("manage-require-screen-share").checked,
      block_clipboard: document.getElementById("manage-block-clipboard").checked,
    }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    showToast(typeof body.detail === "string" ? body.detail : "Không lưu được kỳ thi.", "error");
    return;
  }
  managedExam = body;
  renderManagedExam();
  showToast("Đã lưu kỳ thi.", "success");
  await loadReadiness();
});

document.getElementById("assignment-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/assignments`, {
    method: "PUT",
    body: JSON.stringify({
      user_id: document.getElementById("assignment-user").value,
      assignment_role: document.getElementById("assignment-role").value,
      expires_at: isoFromManageInput(document.getElementById("assignment-expiry").value),
    }),
  });
  showToast(response.ok ? "Đã phân công." : "Không phân công được.", response.ok ? "success" : "error");
  if (response.ok) await loadAssignments();
});

async function initializeExamManage() {
  if (!MANAGE_EXAM_ID) throw new Error("Thiếu mã kỳ thi để tải thông tin quản lý.");
  if (!await API.requireAuth()) return;
  await loadManagePolicyFloor();
  await loadManagedExam();
  if (!(managedExam.allowed_actions || []).includes("exam.manage")) {
    window.location.replace(`/ui/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/detail`);
    return;
  }
  await Promise.all([loadEligibleMembers(), loadReadiness()]);
  await loadAssignments();
}

initializeExamManage().catch((error) => showToast(error.message, "error"));
document.getElementById("manage-auth-mode").addEventListener("change", syncManageAuthMode);
document.getElementById("manage-require-extension").addEventListener("change", syncManageAuthMode);
document.getElementById("manage-rotate-code").addEventListener("click", () => {
  rotateManagedJoinCode().catch((error) => showToast(error.message, "error"));
});
