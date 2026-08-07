let managedExam = null;
let canAssign = false;

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
}

function renderManagedExam() {
  document.getElementById("manage-exam-title").textContent = managedExam.name;
  document.getElementById("manage-exam-state").textContent = `Trạng thái: ${managedExam.status} · phiên bản ${managedExam.version}`;
  document.getElementById("manage-exam-name").value = managedExam.name;
  document.getElementById("manage-exam-start").value = localInputValue(managedExam.scheduled_start_at);
  document.getElementById("manage-exam-end").value = localInputValue(managedExam.scheduled_end_at);
  document.getElementById("exam-config-form").querySelectorAll("input,button").forEach((element) => {
    element.disabled = managedExam.status !== "draft";
  });
  const transitions = {
    draft: ["scheduled", "open", "archived"],
    scheduled: ["draft", "open", "closed"],
    open: ["closed"],
    closed: ["open", "archived"],
    archived: [],
  };
  const labels = { draft: "Về bản nháp", scheduled: "Lên lịch", open: "Mở", closed: "Đóng", archived: "Lưu trữ" };
  const buttons = (transitions[managedExam.status] || []).map((status) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = labels[status];
    button.addEventListener("click", () => setLifecycle(status));
    return button;
  });
  document.getElementById("lifecycle-actions").replaceChildren(...buttons);
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
    manageCell(row, assignment.assignment_role);
    manageCell(row, assignment.status);
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
      scheduled_start_at: document.getElementById("manage-exam-start").value || null,
      scheduled_end_at: document.getElementById("manage-exam-end").value || null,
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
});

document.getElementById("assignment-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await API.request(`/exams/${encodeURIComponent(MANAGE_EXAM_ID)}/assignments`, {
    method: "PUT",
    body: JSON.stringify({
      user_id: document.getElementById("assignment-user").value,
      assignment_role: document.getElementById("assignment-role").value,
    }),
  });
  showToast(response.ok ? "Đã phân công." : "Không phân công được.", response.ok ? "success" : "error");
  if (response.ok) await loadAssignments();
});

async function initializeExamManage() {
  if (!await API.requireAuth()) return;
  await Promise.all([loadManagedExam(), loadEligibleMembers()]);
  await loadAssignments();
}

initializeExamManage().catch((error) => showToast(error.message, "error"));
