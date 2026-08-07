let currentUser = null;

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
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleString("vi-VN");
}

async function setExamStatus(examId, status) {
  const response = await API.request(`/exams/${encodeURIComponent(examId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  if (!response.ok) {
    showToast("Không cập nhật được trạng thái kỳ thi.", "error");
    return;
  }
  showToast(status === "open" ? "Đã mở kỳ thi." : "Đã đóng kỳ thi.", "success");
  await loadExams();
}

async function rotateJoinCode(examId) {
  const response = await API.request(`/exams/${encodeURIComponent(examId)}/rotate-code`, {
    method: "POST",
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

  if (API.hasCapability("exam.manage")) {
    const manageLink = document.createElement("a");
    manageLink.href = `/ui/exams/${encodeURIComponent(exam.id)}/manage`;
    manageLink.textContent = "Quản lý";
    actions.append(document.createTextNode(" · "), manageLink);
    const statusButton = document.createElement("button");
    statusButton.type = "button";
    statusButton.className = "link-button";
    statusButton.textContent = exam.status === "open" ? "Đóng" : "Mở";
    statusButton.addEventListener("click", () => setExamStatus(
      exam.id, exam.status === "open" ? "closed" : "open",
    ));
    const rotateButton = document.createElement("button");
    rotateButton.type = "button";
    rotateButton.className = "link-button";
    rotateButton.textContent = "Đổi mã";
    rotateButton.addEventListener("click", () => rotateJoinCode(exam.id));
    actions.append(document.createTextNode(" · "), statusButton, document.createTextNode(" · "), rotateButton);
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

document.getElementById("create-exam-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const nameInput = document.getElementById("exam-name");
  const authMode = document.getElementById("candidate-auth-mode").value;
  const payload = {
    name: nameInput.value,
    initial_status: document.getElementById("initial-status").value,
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
    nameInput.value = "";
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
    await loadExams();
  } catch (error) {
    showToast(error.message || "Không tải được danh sách kỳ thi.", "error");
  }
}

initializeExams();

document.getElementById("candidate-auth-mode").addEventListener("change", (event) => {
  const google = event.target.value === "google";
  document.getElementById("google-domain-wrap").classList.toggle("hidden", !google);
  const requireExtension = document.getElementById("require-extension");
  requireExtension.checked = google || requireExtension.checked;
  requireExtension.disabled = google;
});
