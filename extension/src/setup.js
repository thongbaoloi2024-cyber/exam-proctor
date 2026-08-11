"use strict";

const ext = globalThis.browser || globalThis.chrome;
const BACKEND_URL = "http://localhost:8000";
const SETUP_DRAFT_KEY = "dattSetupDraft";
let currentPolicy = null;
let googleProfile = null;
const preflight = new Map();

function element(id) { return document.getElementById(id); }

function setStatus(id, text, kind = "") {
  const node = element(id);
  node.textContent = text;
  node.className = `status${kind ? ` ${kind}` : ""}`;
}

function setPreflight(key, label, state, help = "") {
  preflight.set(key, { label, state, help });
  const list = element("preflight-list");
  list.replaceChildren(...[...preflight.values()].map((step) => {
    const item = document.createElement("li");
    item.className = `preflight-${step.state}`;
    item.textContent = `${step.state === "ok" ? "✓" : step.state === "error" ? "!" : "…"} ${step.label}${step.help ? ` — ${step.help}` : ""}`;
    return item;
  }));
}

async function requestOriginPermissions(urls) {
  const origins = [...new Set(urls.filter(Boolean).map(DATT.originPattern))];
  if (!origins.length) return true;
  if (await ext.permissions.contains({ origins })) return true;
  return ext.permissions.request({ origins });
}

async function saveSetupDraft(joinCode) {
  await ext.storage.session.set({ [SETUP_DRAFT_KEY]: { joinCode } });
}

async function send(message) {
  const response = await ext.runtime.sendMessage(message);
  if (!response?.ok) throw Object.assign(new Error(response?.error || "Extension không phản hồi."), { status: response?.status });
  return response;
}

function renderPolicy(policy) {
  currentPolicy = policy;
  element("policy-card").classList.remove("hidden");
  element("exam-name").textContent = `2. ${policy.exam_name}`;
  element("manual-fields").classList.toggle("hidden", policy.candidate_auth_mode !== "manual");
  element("google-fields").classList.toggle("hidden", policy.candidate_auth_mode !== "google");
  const labels = [
    `Xác thực: ${policy.candidate_auth_mode === "google" ? "Tài khoản Google" : "Họ tên + mã thí sinh"}`,
    policy.require_camera ? "Camera bắt buộc" : "Không bắt buộc camera",
    policy.require_microphone ? "Microphone bắt buộc" : "Không thu microphone",
    policy.require_screen_share ? "Chia sẻ toàn bộ màn hình bắt buộc" : "Không bắt buộc chia sẻ màn hình",
    policy.require_fullscreen ? "Trang thi phải ở toàn màn hình" : "Không bắt buộc toàn màn hình",
    policy.block_clipboard ? "Chặn và ghi nhận copy/paste/menu chuột phải" : "Không chặn clipboard",
    `Rời cửa sổ quá ${policy.max_focus_loss_seconds} giây sẽ thành cảnh báo cao`,
  ];
  element("policy-list").replaceChildren(...labels.map((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    return item;
  }));
  const driftSeconds = Math.abs(Date.now() - Date.parse(policy.server_time)) / 1000;
  setPreflight("version", `Extension ${DATT.VERSION} (yêu cầu ≥ ${policy.min_extension_version})`, DATT.compareVersions(DATT.VERSION, policy.min_extension_version) >= 0 ? "ok" : "error", "Cập nhật extension nếu chưa đạt phiên bản tối thiểu");
  setPreflight("network", "Kết nối backend", "ok");
  setPreflight("clock", "Đồng hồ thiết bị", driftSeconds <= 120 ? "ok" : "error", driftSeconds > 120 ? "Bật đồng bộ ngày giờ tự động" : "");
  setPreflight("permissions", "Quyền truy cập trang thi", "pending", "Sẽ yêu cầu khi tham gia");
  setPreflight("media", "Camera và microphone", policy.require_camera || policy.require_microphone ? "pending" : "ok", "Sẽ kiểm tra khi tham gia");
  setPreflight("screen", "Chia sẻ màn hình", policy.require_screen_share ? "pending" : "ok", policy.require_screen_share ? "Chọn toàn bộ màn hình trong bảng giám sát" : "Không bắt buộc");
  if (driftSeconds > 120) {
    setStatus("join-status", "Đồng hồ máy lệch backend quá 2 phút; hãy đồng bộ thời gian trước khi thi.", "error");
  }
}

function renderGoogleProfile(profile) {
  googleProfile = profile;
  element("google-profile").classList.toggle("hidden", !profile);
  element("google-logout").classList.toggle("hidden", !profile);
  element("google-login").textContent = profile ? "Đổi tài khoản Google" : "Đăng nhập bằng Google";
  element("google-name").textContent = profile?.display_name || "";
  element("google-email").textContent = profile?.email || "";
}

async function checkRequiredMedia(policy) {
  if (!policy.require_camera && !policy.require_microphone) return;
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("Trình duyệt không hỗ trợ camera/microphone cho extension.");
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: Boolean(policy.require_camera),
      audio: Boolean(policy.require_microphone),
    });
  } catch (_error) {
    throw new Error("Không thể cấp camera/microphone bắt buộc. Hãy kiểm tra quyền của extension.");
  } finally {
    stream?.getTracks().forEach((track) => track.stop());
  }
}

element("check-code").addEventListener("click", async () => {
  const joinCode = element("join-code").value.trim().toUpperCase();
  setStatus("setup-status", "Đang kiểm tra...");
  try {
    DATT.normalizeBaseUrl(BACKEND_URL);
    await saveSetupDraft(joinCode);
    if (!(await requestOriginPermissions([BACKEND_URL]))) {
      throw new Error("Bạn chưa cấp quyền truy cập backend.");
    }
    const { policy } = await send({ type: "DATT_GET_POLICY", baseUrl: BACKEND_URL, joinCode });
    renderPolicy(policy);
    if (policy.candidate_auth_mode === "google") {
      if (!policy.google_login_available) throw new Error("Backend chưa cấu hình Google OAuth cho kỳ thi này.");
      const { profile } = await send({ type: "DATT_GET_CANDIDATE", baseUrl: BACKEND_URL });
      renderGoogleProfile(profile);
    }
    setStatus("setup-status", "Mã hợp lệ.", "success");
  } catch (error) {
    currentPolicy = null;
    element("policy-card").classList.add("hidden");
    setStatus("setup-status", error.message, "error");
  }
});

element("google-login").addEventListener("click", async () => {
  setStatus("join-status", "Đang mở đăng nhập Google...");
  try {
    const { profile } = await send({
      type: "DATT_GOOGLE_LOGIN",
      baseUrl: BACKEND_URL,
    });
    renderGoogleProfile(profile);
    setStatus("join-status", "Đã xác minh tài khoản Google.", "success");
  } catch (error) {
    setStatus("join-status", error.message, "error");
  }
});

element("google-logout").addEventListener("click", async () => {
  try {
    await send({ type: "DATT_GOOGLE_LOGOUT", baseUrl: BACKEND_URL });
    renderGoogleProfile(null);
    setStatus("join-status", "Đã xóa phiên đăng nhập lưu trên thiết bị.", "success");
  } catch (error) {
    setStatus("join-status", error.message, "error");
  }
});

element("join-exam").addEventListener("click", async () => {
  if (!currentPolicy) return setStatus("join-status", "Hãy kiểm tra mã tham gia trước.", "error");
  if (!element("consent").checked) return setStatus("join-status", "Bạn cần xác nhận chính sách giám sát.", "error");
  if (currentPolicy.candidate_auth_mode === "google" && !googleProfile) {
    return setStatus("join-status", "Hãy đăng nhập Google trước.", "error");
  }
  const studentName = element("student-name").value.trim();
  const candidateId = element("candidate-id").value.trim();
  if (currentPolicy.candidate_auth_mode === "manual" && (!studentName || !candidateId)) {
    return setStatus("join-status", "Vui lòng nhập đủ họ tên và mã thí sinh.", "error");
  }

  element("join-exam").disabled = true;
  setStatus("join-status", "Đang kiểm tra thiết bị và tạo phiên...");
  try {
    const urls = [BACKEND_URL, currentPolicy.exam_url].filter(Boolean);
    if (!(await requestOriginPermissions(urls))) {
      setPreflight("permissions", "Quyền truy cập trang thi", "error", "Mở cài đặt extension và cấp quyền cho backend/trang thi");
      throw new Error("Chưa cấp quyền truy cập trang bài thi.");
    }
    setPreflight("permissions", "Quyền truy cập trang thi", "ok");
    await checkRequiredMedia(currentPolicy);
    setPreflight("media", "Camera và microphone", "ok");
    const { session } = await send({
      type: "DATT_JOIN_EXAM",
      baseUrl: BACKEND_URL,
      joinCode: element("join-code").value,
      studentName,
      candidateId,
    });
    setStatus("join-status", `${session.resumed ? "Đã khôi phục" : "Đã tạo"} phiên ${session.supportCode || session.sessionId.slice(0, 8)}. Hãy kích hoạt bảng giám sát trên trang thi.`, "success");
    element("join-card").classList.add("hidden");
  } catch (error) {
    setStatus("join-status", error.message, "error");
  } finally {
    element("join-exam").disabled = false;
  }
});

async function initialize() {
  const [{ session }, storedDraft] = await Promise.all([
    send({ type: "DATT_GET_ACTIVE" }),
    ext.storage.session.get(SETUP_DRAFT_KEY),
  ]);
  const draft = storedDraft[SETUP_DRAFT_KEY];
  if (draft?.joinCode) element("join-code").value = draft.joinCode;
  if (session) {
    element("active-card").classList.remove("hidden");
    element("join-card").classList.add("hidden");
    renderActive(session);
  }
}

function renderActive(session) {
  element("active-summary").textContent = `${session.examName} · ${session.studentName} · Mã hỗ trợ ${session.supportCode}`;
  const rows = [
    [session.connected, session.connected ? "WebSocket đã kết nối" : "Đang kết nối lại backend"],
    [session.mediaReady, session.mediaReady ? "Thiết bị giám sát đã sẵn sàng" : "Chưa kích hoạt camera/màn hình"],
    [session.pendingEventCount === 0, `${session.pendingEventCount} sự kiện đang chờ đồng bộ`],
    [Boolean(session.lastSyncedAt), session.lastSyncedAt ? `Đồng bộ cuối: ${new Date(session.lastSyncedAt).toLocaleTimeString("vi-VN")}` : "Chưa đồng bộ sự kiện"],
  ];
  element("active-health").replaceChildren(...rows.map(([ok, text]) => {
    const item = document.createElement("li"); item.className = ok ? "preflight-ok" : "preflight-pending"; item.textContent = `${ok ? "✓" : "…"} ${text}`; return item;
  }));
}

element("return-exam").addEventListener("click", async () => {
  try { const { session } = await send({ type: "DATT_OPEN_ACTIVE" }); renderActive(session); window.close(); } catch (error) { setStatus("setup-status", error.message, "error"); }
});
element("open-monitor").addEventListener("click", async () => {
  try { const { session } = await send({ type: "DATT_OPEN_ACTIVE" }); renderActive(session); } catch (error) { setStatus("setup-status", error.message, "error"); }
});
element("end-active").addEventListener("click", async () => {
  if (!confirm("Bạn chắc chắn muốn kết thúc phiên? Hãy bảo đảm các sự kiện đã đồng bộ.")) return;
  try { await send({ type: "DATT_END_SESSION", reason: "completed" }); element("active-card").classList.add("hidden"); element("join-card").classList.remove("hidden"); setStatus("setup-status", "Phiên đã kết thúc.", "success"); } catch (error) { setStatus("setup-status", error.message, "error"); }
});

initialize().catch((error) => setStatus("setup-status", error.message, "error"));
