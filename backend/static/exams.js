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

function formatExamDate(value, dateOnly = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "–";
  return new Intl.DateTimeFormat("vi-VN", dateOnly
    ? { dateStyle: "short" }
    : { dateStyle: "short", timeStyle: "short" }).format(date);
}

function setCreateExamPanelOpen(open) {
  const form = document.getElementById("create-exam-form");
  const toggle = document.getElementById("create-exam-toggle");
  form.classList.toggle("hidden", !open);
  toggle.setAttribute("aria-expanded", String(open));
  toggle.classList.toggle("active", open);
  if (open) {
    setWizardStep(0);
    document.getElementById("exam-name").focus();
  }
}

async function resetAndCloseCreateExam() {
  const form = document.getElementById("create-exam-form");
  form.reset();
  if (API.hasCapability("exam.create")) await loadDefaultExamPolicy();
  setWizardStep(0);
  setCreateExamPanelOpen(false);
}

function examPinButton(exam) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `exam-pin-button${exam.is_pinned ? " pinned" : ""}`;
  button.textContent = "📌";
  const action = exam.is_pinned ? "Bỏ ghim" : "Ghim";
  button.title = `${action} ${exam.name}`;
  button.setAttribute("aria-label", `${action} ${exam.name}`);
  button.setAttribute("aria-pressed", String(Boolean(exam.is_pinned)));
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await API.setExamPinned(exam.id, !exam.is_pinned);
      showToast(
        exam.is_pinned ? `Đã bỏ ghim “${exam.name}”.` : `Đã ghim “${exam.name}”.`,
        "success",
      );
    } catch (error) {
      button.disabled = false;
      showToast(error.message || "Không cập nhật được ghim kỳ thi.", "error");
    }
  });
  return button;
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

function buildExamRow(exam) {
  const breakGlassView = Boolean(currentUser?.is_system_admin);
  const row = document.createElement("tr");
  const nameCell = document.createElement("td");
  nameCell.className = "exam-name-cell";
  if (!breakGlassView) nameCell.appendChild(examPinButton(exam));
  const examName = document.createElement("a");
  examName.href = `/ui/exams/${encodeURIComponent(exam.id)}/detail`;
  examName.className = "exam-name-link";
  examName.textContent = exam.name;
  nameCell.appendChild(examName);
  row.appendChild(nameCell);
  appendTextCell(row, formatExamDate(exam.created_at, true));
  appendTextCell(row, formatExamDate(exam.updated_at));
  appendTextCell(row, exam.candidate_auth_mode === "google" ? "Google" : "Họ tên + mã thí sinh");

  const statusLabels = {
    draft: "Bản nháp",
    scheduled: "Đã lên lịch",
    open: "Đang mở",
    closed: "Đã đóng",
    archived: "Đã lưu trữ",
  };
  const statusCell = document.createElement("td");
  const statusBadge = document.createElement("span");
  statusBadge.className = `exam-status-badge status-${exam.status}`;
  statusBadge.textContent = statusLabels[exam.status] || exam.status;
  statusCell.appendChild(statusBadge);
  row.appendChild(statusCell);

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
    const expiry = document.createElement("small");
    expiry.className = "exam-code-expiry muted";
    expiry.textContent = formatExpiry(exam.join_code_expires_at);
    codeCell.appendChild(expiry);
  }
  row.appendChild(codeCell);

  const actions = document.createElement("td");
  actions.className = "exam-row-actions";

  const allowedActions = new Set(exam.allowed_actions || []);
  const allowedTransitions = new Set(exam.allowed_transitions || []);
  if (allowedActions.has("exam.manage")) {
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
      actions.appendChild(statusButton);
    }
  }
  const detailLink = document.createElement("a");
  detailLink.href = `/ui/exams/${encodeURIComponent(exam.id)}/detail`;
  detailLink.textContent = "Chi tiết";
  actions.appendChild(detailLink);
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
        : "Chưa có kỳ thi nào. Nhấn nút + để tạo kỳ thi đầu tiên.",
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
    await resetAndCloseCreateExam();
    await loadExams();
    await API.loadPinnedExams({ forceOpen: true });
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
    window.location.replace("/ui/organization/overview");
    return;
  }
  if (currentUser.is_system_admin) {
    document.getElementById("exams-page-title").textContent = "Dữ liệu break-glass";
    document.getElementById("exams-page-description").classList.remove("hidden");
    document.getElementById("exam-code-heading").textContent = "Mã tham gia (đã ẩn)";
  }
  const createExamForm = document.getElementById("create-exam-form");
  const canCreateExam = API.hasCapability("exam.create");
  createExamForm.classList.add("hidden");
  document.getElementById("create-exam-toggle").classList.toggle("hidden", !canCreateExam);
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

document.addEventListener("exam-pin-changed", () => {
  if (!currentUser || currentUser.is_system_admin) return;
  loadExams().catch((error) => showToast(error.message || "Không tải lại được danh sách kỳ thi.", "error"));
});

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
document.getElementById("create-exam-toggle").addEventListener("click", () => {
  const expanded = document.getElementById("create-exam-toggle").getAttribute("aria-expanded") === "true";
  if (expanded) resetAndCloseCreateExam().catch((error) => showToast(error.message, "error"));
  else setCreateExamPanelOpen(true);
});
document.getElementById("create-exam-close").addEventListener("click", () => {
  resetAndCloseCreateExam().catch((error) => showToast(error.message, "error"));
});
document.getElementById("create-exam-cancel").addEventListener("click", () => {
  resetAndCloseCreateExam().catch((error) => showToast(error.message, "error"));
});
setWizardStep(0);
