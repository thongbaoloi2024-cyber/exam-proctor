let currentUser = null;
let organizationPolicyFloor = null;
let wizardStep = 0;

async function copyJoinCode(code) {
  try {
    await navigator.clipboard.writeText(code);
    showToast(`Đã sao chép mã tham gia: ${code}`, "success");
  } catch (error) {
    showToast(`Mã tham gia: ${code} (trình duyệt không hỗ trợ tự chép)`, "info");
  }
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
  cell.colSpan = 6;
  cell.className = "muted";
  cell.textContent = message;
  row.appendChild(cell);
  tbody.replaceChildren(row);
}

function formatExpiry(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const remainingMinutes = Math.floor((date.getTime() - Date.now()) / 60_000);
  if (remainingMinutes <= 0) return `${date.toLocaleString("vi-VN")} · đã hết hạn`;
  const hours = Math.floor(remainingMinutes / 60);
  const minutes = remainingMinutes % 60;
  return `${date.toLocaleString("vi-VN")} · còn ${hours}h ${minutes}m`;
}

async function setExamStatus(examId, status, expectedVersion) {
  const response = await API.request(`/exams/${encodeURIComponent(examId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, expected_version: expectedVersion }),
  });
  if (!response.ok) {
    showToast("Không cập nhật được trạng thái kỳ thi.", "error");
    return;
  }
  showToast(status === "open" ? "Đã mở kỳ thi." : "Đã đóng kỳ thi.", "success");
  await loadExams();
}

async function rotateJoinCode(examId, expectedVersion) {
  const requestedHours = window.prompt("Thời hạn mã mới (giờ, từ 0.1 đến 168):", "24");
  if (requestedHours == null) return;
  const ttlMinutes = Math.round(Number(requestedHours) * 60);
  if (!Number.isFinite(ttlMinutes) || ttlMinutes < 5 || ttlMinutes > 10080) {
    showToast("Thời hạn mã phải từ 5 phút đến 7 ngày.", "error");
    return;
  }
  const response = await API.request(`/exams/${encodeURIComponent(examId)}/rotate-code`, {
    method: "POST",
    body: JSON.stringify({ expected_version: expectedVersion, ttl_minutes: ttlMinutes }),
  });
  if (!response.ok) {
    showToast("Không tạo lại được mã tham gia.", "error");
    return;
  }
  showToast("Đã tạo mã tham gia mới; mã cũ không còn hiệu lực.", "success");
  await loadExams();
}

function buildExamRow(exam) {
  const breakGlassView = Boolean(currentUser?.is_system_admin);
  const row = document.createElement("tr");
  appendTextCell(row, exam.name);
  appendTextCell(row, exam.candidate_auth_mode === "google" ? "Google" : "Họ tên + mã thí sinh");

  const codeCell = document.createElement("td");
  if (breakGlassView || !exam.join_code) {
    codeCell.textContent = "Đã ẩn";
    codeCell.className = "muted";
  } else {
    const code = document.createElement("code");
    code.textContent = exam.join_code;
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "link-button copy-btn";
    copyButton.textContent = "Chép";
    copyButton.addEventListener("click", () => copyJoinCode(exam.join_code));
    codeCell.append(code, document.createTextNode(" "), copyButton);
  }
  row.appendChild(codeCell);

  const statusLabels = {
    draft: "Bản nháp",
    scheduled: "Đã lên lịch",
    open: "Đang mở",
    closed: "Đã đóng",
    archived: "Đã lưu trữ",
  };
  appendTextCell(row, statusLabels[exam.status] || exam.status);
  appendTextCell(row, formatExpiry(exam.join_code_expires_at));

  const actions = document.createElement("td");
  const dashboardLink = document.createElement("a");
  dashboardLink.href = `/ui/exams/${encodeURIComponent(exam.id)}/dashboard`;
  dashboardLink.textContent = "Dashboard";
  actions.appendChild(dashboardLink);

  const allowedActions = new Set(exam.allowed_actions || []);
  const allowedTransitions = new Set(exam.allowed_transitions || []);
  if (allowedActions.has("exam.manage")) {
    const manageLink = document.createElement("a");
    manageLink.href = `/ui/exams/${encodeURIComponent(exam.id)}/manage`;
    manageLink.textContent = "Quản lý";
    actions.append(document.createTextNode(" · "), manageLink);
    const quickStatus = exam.status === "open"
      ? (allowedTransitions.has("closed") ? "closed" : null)
      : (allowedTransitions.has("open") ? "open" : null);
    if (quickStatus) {
      const statusButton = document.createElement("button");
      statusButton.type = "button";
      statusButton.className = "link-button";
      statusButton.textContent = quickStatus === "closed" ? "Đóng" : "Mở";
      statusButton.addEventListener("click", () => setExamStatus(
        exam.id,
        quickStatus,
        exam.version,
      ));
      actions.append(document.createTextNode(" · "), statusButton);
    }
    if (exam.status !== "archived") {
      const rotateButton = document.createElement("button");
      rotateButton.type = "button";
      rotateButton.className = "link-button";
      rotateButton.textContent = "Đổi mã";
      rotateButton.addEventListener("click", () => rotateJoinCode(exam.id, exam.version));
      actions.append(document.createTextNode(" · "), rotateButton);
    }
  }
  row.appendChild(actions);
  return row;
}

async function loadExams() {
  const tbody = document.querySelector("#exams-table tbody");
  showTableMessage(tbody, "Đang tải...");
  const response = await API.request("/exams");
  if (!response.ok) throw new Error("Không tải được danh sách kỳ thi.");
  const exams = await response.json();
  if (exams.length === 0) {
    showTableMessage(
      tbody,
      currentUser?.is_system_admin
        ? "Không có kỳ thi thuộc quyền break-glass đang hiệu lực."
        : "Chưa có kỳ thi nào - tạo kỳ thi đầu tiên ở trên.",
    );
    return;
  }
  tbody.replaceChildren(...exams.map(buildExamRow));
}

async function loadDefaultExamPolicy() {
  const response = await API.request("/exams/policy/defaults");
  if (!response.ok) throw new Error("Không tải được chính sách mặc định của tổ chức.");
  const policy = await response.json();
  organizationPolicyFloor = policy;
  document.getElementById("candidate-auth-mode").value = policy.default_candidate_auth_mode;
  document.getElementById("min-extension-version").value = policy.min_extension_version;
  document.getElementById("max-focus-loss").value = policy.max_focus_loss_seconds;
  document.getElementById("require-extension").checked = policy.require_extension;
  document.getElementById("require-fullscreen").checked = policy.require_fullscreen;
  document.getElementById("require-camera").checked = policy.require_camera;
  document.getElementById("require-microphone").checked = policy.require_microphone;
  document.getElementById("require-screen-share").checked = policy.require_screen_share;
  document.getElementById("block-clipboard").checked = policy.block_clipboard;
  [
    ["require-extension", "require_extension"],
    ["require-fullscreen", "require_fullscreen"],
    ["require-camera", "require_camera"],
    ["require-microphone", "require_microphone"],
    ["require-screen-share", "require_screen_share"],
    ["block-clipboard", "block_clipboard"],
  ].forEach(([elementId, policyField]) => {
    document.getElementById(elementId).disabled = Boolean(policy[policyField]);
  });
  document.getElementById("max-focus-loss").max = String(policy.max_focus_loss_seconds);
  syncExamAuthMode();
  syncCreateRequirements();
}

function setWizardStep(nextStep) {
  wizardStep = Math.max(0, Math.min(3, nextStep));
  document.querySelectorAll("[data-wizard-step]").forEach((step) => {
    step.classList.toggle("hidden", Number(step.dataset.wizardStep) !== wizardStep);
  });
  document.querySelectorAll("[data-wizard-indicator]").forEach((indicator) => {
    indicator.classList.toggle("active", Number(indicator.dataset.wizardIndicator) === wizardStep);
  });
  document.getElementById("wizard-previous").classList.toggle("hidden", wizardStep === 0);
  document.getElementById("wizard-next").classList.toggle("hidden", wizardStep === 3);
  document.getElementById("create-exam-submit").classList.toggle("hidden", wizardStep !== 3);
  if (wizardStep === 3) renderExamReview();
}

function currentWizardStepIsValid() {
  const step = document.querySelector(`[data-wizard-step="${wizardStep}"]`);
  const controls = Array.from(step.querySelectorAll("input,select,textarea"));
  const invalid = controls.find((control) => !control.checkValidity());
  if (invalid) {
    invalid.reportValidity();
    return false;
  }
  return true;
}

function reviewItem(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = value;
  wrapper.append(term, detail);
  return wrapper;
}

function isoFromLocalInput(value) {
  return value ? new Date(value).toISOString() : null;
}

function renderExamReview() {
  const deviceLabels = [
    ["require-extension", "Extension"],
    ["require-fullscreen", "Fullscreen"],
    ["require-camera", "Camera"],
    ["require-microphone", "Microphone"],
    ["require-screen-share", "Chia sẻ màn hình"],
    ["block-clipboard", "Chặn clipboard"],
  ].filter(([id]) => document.getElementById(id).checked).map(([, label]) => label);
  document.getElementById("create-exam-review").replaceChildren(
    reviewItem("Tên kỳ thi", document.getElementById("exam-name").value || "–"),
    reviewItem("Trạng thái", document.getElementById("initial-status").selectedOptions[0].textContent),
    reviewItem("Xác thực", document.getElementById("candidate-auth-mode").selectedOptions[0].textContent),
    reviewItem("URL", document.getElementById("exam-url").value || "Không dùng"),
    reviewItem("Mã tham gia", `${document.getElementById("join-code-ttl").value} phút`),
    reviewItem("Yêu cầu thiết bị", deviceLabels.join(", ") || "Không bắt buộc"),
  );
}

function syncCreateRequirements() {
  const scheduled = document.getElementById("initial-status").value === "scheduled";
  document.getElementById("create-start-wrap").classList.toggle("hidden", !scheduled);
  document.getElementById("create-end-wrap").classList.toggle("hidden", !scheduled);
  document.getElementById("create-exam-start").required = scheduled;
  document.getElementById("create-exam-end").required = scheduled;
  document.getElementById("exam-url").required = document.getElementById("require-extension").checked;
}

document.getElementById("create-exam-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const nameInput = document.getElementById("exam-name");
  const authMode = document.getElementById("candidate-auth-mode").value;
  const payload = {
    name: nameInput.value,
    initial_status: document.getElementById("initial-status").value,
    scheduled_start_at: isoFromLocalInput(document.getElementById("create-exam-start").value),
    scheduled_end_at: isoFromLocalInput(document.getElementById("create-exam-end").value),
    join_code_ttl_minutes: Number(document.getElementById("join-code-ttl").value),
    candidate_auth_mode: authMode,
    exam_url: document.getElementById("exam-url").value,
    require_extension: document.getElementById("require-extension").checked,
    min_extension_version: document.getElementById("min-extension-version").value,
    require_fullscreen: document.getElementById("require-fullscreen").checked,
    require_camera: document.getElementById("require-camera").checked,
    require_microphone: document.getElementById("require-microphone").checked,
    require_screen_share: document.getElementById("require-screen-share").checked,
    block_clipboard: document.getElementById("block-clipboard").checked,
    max_focus_loss_seconds: Number(document.getElementById("max-focus-loss").value),
    google_allowed_domain: authMode === "google"
      ? (document.getElementById("google-domain").value.trim() || null)
      : null,
  };
  const response = await API.request("/exams", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (response.ok) {
    showToast(`Đã tạo kỳ thi "${nameInput.value}"`, "success");
    event.target.reset();
    await loadDefaultExamPolicy();
    setWizardStep(0);
    await loadExams();
  } else {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
    showToast(detail || "Không tạo được kỳ thi.", "error");
  }
});

async function initializeExams() {
  currentUser = await API.requireAuth();
  if (!currentUser) return;
  if (currentUser.effective_role === "org_admin" || currentUser.role === "admin") {
    window.location.replace("/ui/organization");
    return;
  }
  if (currentUser.is_system_admin) {
    document.getElementById("exams-page-title").textContent = "Dữ liệu break-glass";
    document.getElementById("exams-page-description").classList.remove("hidden");
    document.getElementById("exam-code-heading").textContent = "Mã tham gia (đã ẩn)";
  }
  const createExamForm = document.getElementById("create-exam-form");
  createExamForm.classList.toggle("hidden", !API.hasCapability("exam.create"));
  document.getElementById("organization-admin-hint").classList.toggle(
    "hidden",
    !API.hasCapability("org.members.manage"),
  );
  try {
    if (API.hasCapability("exam.create")) await loadDefaultExamPolicy();
    await loadExams();
  } catch (error) {
    showToast(error.message || "Không tải được danh sách kỳ thi.", "error");
  }
}

initializeExams();

function syncExamAuthMode() {
  const google = document.getElementById("candidate-auth-mode").value === "google";
  document.getElementById("google-domain-wrap").classList.toggle("hidden", !google);
  const requireExtension = document.getElementById("require-extension");
  requireExtension.checked = google || requireExtension.checked;
  requireExtension.disabled = google || Boolean(organizationPolicyFloor?.require_extension);
  syncCreateRequirements();
}

document.getElementById("candidate-auth-mode").addEventListener("change", syncExamAuthMode);
document.getElementById("initial-status").addEventListener("change", syncCreateRequirements);
document.getElementById("require-extension").addEventListener("change", syncCreateRequirements);
document.getElementById("wizard-next").addEventListener("click", () => {
  if (currentWizardStepIsValid()) setWizardStep(wizardStep + 1);
});
document.getElementById("wizard-previous").addEventListener("click", () => setWizardStep(wizardStep - 1));
setWizardStep(0);
