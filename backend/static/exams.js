let currentUser = null;
let organizationPolicyFloor = null;
let wizardStep = 0;
let allExams = [];
let currentExamPage = 1;
const EXAMS_PAGE_SIZE = 15;
const EXAM_STATUS_LABELS = {
  draft: "Bản nháp",
  scheduled: "Đã lên lịch",
  open: "Đang mở",
  closed: "Đã đóng",
  archived: "Đã lưu trữ",
};
const EXAM_STATUS_ORDER = {
  open: 0,
  scheduled: 1,
  draft: 2,
  closed: 3,
  archived: 4,
};
const EXAM_SORT_DEFAULT_DIRECTIONS = {
  name: "ascending",
  created_at: "descending",
  updated_at: "descending",
  candidate_auth_mode: "ascending",
  status: "ascending",
  join_code: "ascending",
};
const examNameCollator = new Intl.Collator("vi", { numeric: true, sensitivity: "base" });
let examSort = { key: "status", direction: "ascending" };

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

function formatExamDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "–";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
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
  const pagination = document.getElementById("exam-pagination");
  pagination.classList.add("hidden");
  pagination.replaceChildren();
}

function examAuthLabel(exam) {
  return exam.candidate_auth_mode === "google" ? "Google" : "Họ tên + mã thí sinh";
}

function examTimestamp(value) {
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function compareExamValues(left, right, key) {
  if (key === "status") {
    const leftRank = EXAM_STATUS_ORDER[left.status] ?? Number.MAX_SAFE_INTEGER;
    const rightRank = EXAM_STATUS_ORDER[right.status] ?? Number.MAX_SAFE_INTEGER;
    return leftRank - rightRank;
  }
  if (key === "created_at" || key === "updated_at") {
    return examTimestamp(left[key]) - examTimestamp(right[key]);
  }
  if (key === "candidate_auth_mode") {
    return examNameCollator.compare(examAuthLabel(left), examAuthLabel(right));
  }
  return examNameCollator.compare(String(left[key] || ""), String(right[key] || ""));
}

function sortedExams() {
  const direction = examSort.direction === "ascending" ? 1 : -1;
  return [...allExams].sort((left, right) => {
    const primary = compareExamValues(left, right, examSort.key);
    if (primary !== 0) return primary * direction;

    // Within the same status, the most recently updated exam always comes first.
    if (examSort.key === "status") {
      const updated = examTimestamp(right.updated_at) - examTimestamp(left.updated_at);
      if (updated !== 0) return updated;
    }
    const name = examNameCollator.compare(left.name || "", right.name || "");
    if (name !== 0) return name;
    return String(left.id).localeCompare(String(right.id));
  });
}

function updateExamSortHeaders() {
  document.querySelectorAll("[data-exam-sort]").forEach((button) => {
    const active = button.dataset.examSort === examSort.key;
    const heading = button.closest("th");
    const indicator = button.querySelector(".sort-indicator");
    heading.setAttribute("aria-sort", active ? examSort.direction : "none");
    indicator.textContent = active
      ? (examSort.direction === "ascending" ? "↑" : "↓")
      : "↕";
  });
}

function renderExamPagination(totalItems, totalPages) {
  const pagination = document.getElementById("exam-pagination");
  const firstItem = (currentExamPage - 1) * EXAMS_PAGE_SIZE + 1;
  const lastItem = Math.min(currentExamPage * EXAMS_PAGE_SIZE, totalItems);
  const label = document.createElement("span");
  label.textContent = `Hiển thị ${firstItem}–${lastItem} / ${totalItems} · Trang ${currentExamPage} / ${totalPages}`;

  const actions = document.createElement("div");
  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "secondary-button pagination-button";
  previous.textContent = "← Trước";
  previous.disabled = currentExamPage <= 1;
  previous.addEventListener("click", () => {
    currentExamPage -= 1;
    renderExamTable();
  });

  const next = document.createElement("button");
  next.type = "button";
  next.className = "secondary-button pagination-button";
  next.textContent = "Sau →";
  next.disabled = currentExamPage >= totalPages;
  next.addEventListener("click", () => {
    currentExamPage += 1;
    renderExamTable();
  });
  actions.append(previous, next);
  pagination.replaceChildren(label, actions);
  pagination.classList.remove("hidden");
}

function renderExamTable() {
  const tbody = document.querySelector("#exams-table tbody");
  const exams = sortedExams();
  const totalPages = Math.max(1, Math.ceil(exams.length / EXAMS_PAGE_SIZE));
  currentExamPage = Math.min(Math.max(1, currentExamPage), totalPages);
  const pageStart = (currentExamPage - 1) * EXAMS_PAGE_SIZE;
  tbody.replaceChildren(...exams.slice(pageStart, pageStart + EXAMS_PAGE_SIZE).map(buildExamRow));
  updateExamSortHeaders();
  renderExamPagination(exams.length, totalPages);
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
  const nameContent = document.createElement("div");
  nameContent.className = "exam-name-cell";
  if (!breakGlassView) nameContent.appendChild(examPinButton(exam));
  const examName = document.createElement("a");
  examName.href = `/ui/exams/${encodeURIComponent(exam.id)}/detail`;
  examName.className = "exam-name-link";
  examName.textContent = exam.name;
  nameContent.appendChild(examName);
  nameCell.appendChild(nameContent);
  row.appendChild(nameCell);
  appendTextCell(row, formatExamDate(exam.created_at));
  appendTextCell(row, formatExamDate(exam.updated_at));
  appendTextCell(row, examAuthLabel(exam));

  const statusCell = document.createElement("td");
  const statusBadge = document.createElement("span");
  statusBadge.className = `exam-status-badge status-${exam.status}`;
  statusBadge.textContent = EXAM_STATUS_LABELS[exam.status] || exam.status;
  statusCell.appendChild(statusBadge);
  row.appendChild(statusCell);

  const codeCell = document.createElement("td");
  if (breakGlassView || !exam.join_code) {
    codeCell.textContent = "Đã ẩn";
    codeCell.className = "muted";
  } else {
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "exam-code-copy";
    copyButton.textContent = exam.join_code;
    copyButton.title = `Sao chép mã ${exam.join_code}`;
    copyButton.setAttribute("aria-label", `Sao chép mã tham gia ${exam.join_code}`);
    copyButton.addEventListener("click", () => copyJoinCode(exam.join_code));
    codeCell.appendChild(copyButton);
    const expiry = document.createElement("small");
    expiry.className = "exam-code-expiry muted";
    expiry.textContent = formatExpiry(exam.join_code_expires_at);
    codeCell.appendChild(expiry);
  }
  row.appendChild(codeCell);

  const actionsCell = document.createElement("td");
  const actions = document.createElement("div");
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
  actionsCell.appendChild(actions);
  row.appendChild(actionsCell);
  return row;
}

async function loadExams() {
  const tbody = document.querySelector("#exams-table tbody");
  allExams = [];
  showTableMessage(tbody, "Đang tải...");
  const response = await API.request("/exams");
  if (!response.ok) throw new Error("Không tải được danh sách kỳ thi.");
  const exams = await response.json();
  allExams = exams;
  if (exams.length === 0) {
    showTableMessage(
      tbody,
      currentUser?.is_system_admin
        ? "Không có kỳ thi nào đang được cấp quyền truy cập ngoại lệ."
        : "Chưa có kỳ thi nào. Nhấn nút + để tạo kỳ thi đầu tiên.",
    );
    return;
  }
  currentExamPage = 1;
  renderExamTable();
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
    ["require-extension", "Tiện ích trình duyệt"],
    ["require-fullscreen", "Toàn màn hình"],
    ["require-camera", "Camera"],
    ["require-microphone", "Micrô"],
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
    document.getElementById("exams-page-title").textContent = "Dữ liệu được cấp quyền";
    document.getElementById("exams-page-description").classList.remove("hidden");
    document.querySelector('[data-exam-sort="join_code"] .sort-label').textContent = "Mã tham gia (đã ẩn)";
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
document.querySelectorAll("[data-exam-sort]").forEach((button) => {
  button.addEventListener("click", () => {
    const key = button.dataset.examSort;
    if (examSort.key === key) {
      examSort.direction = examSort.direction === "ascending" ? "descending" : "ascending";
    } else {
      examSort = { key, direction: EXAM_SORT_DEFAULT_DIRECTIONS[key] };
    }
    currentExamPage = 1;
    if (allExams.length) renderExamTable();
    else updateExamSortHeaders();
  });
});
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
