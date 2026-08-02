"use strict";

const ext = globalThis.browser || globalThis.chrome;
let currentPolicy = null;
let googleProfile = null;

function element(id) { return document.getElementById(id); }

function setStatus(id, text, kind = "") {
  const node = element(id);
  node.textContent = text;
  node.className = `status${kind ? ` ${kind}` : ""}`;
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
  const baseUrl = element("backend-url").value;
  const joinCode = element("join-code").value.trim().toUpperCase();
  setStatus("setup-status", "Đang kiểm tra...");
  try {
    DATT.normalizeBaseUrl(baseUrl);
    const permission = await send({ type: "DATT_PREPARE_PERMISSIONS", urls: [baseUrl] });
    if (!permission.granted) throw new Error("Bạn chưa cấp quyền truy cập backend.");
    const { policy } = await send({ type: "DATT_GET_POLICY", baseUrl, joinCode });
    renderPolicy(policy);
    if (policy.candidate_auth_mode === "google") {
      if (!policy.google_login_available) throw new Error("Backend chưa cấu hình Google OAuth cho kỳ thi này.");
      const { profile } = await send({ type: "DATT_GET_CANDIDATE", baseUrl });
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
    const { profile } = await send({ type: "DATT_GOOGLE_LOGIN", baseUrl: element("backend-url").value });
    renderGoogleProfile(profile);
    setStatus("join-status", "Đã xác minh tài khoản Google.", "success");
  } catch (error) {
    setStatus("join-status", error.message, "error");
  }
});

element("google-logout").addEventListener("click", async () => {
  try {
    await send({ type: "DATT_GOOGLE_LOGOUT", baseUrl: element("backend-url").value });
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
    const urls = [element("backend-url").value, currentPolicy.exam_url].filter(Boolean);
    const permission = await send({ type: "DATT_PREPARE_PERMISSIONS", urls });
    if (!permission.granted) throw new Error("Chưa cấp quyền truy cập trang bài thi.");
    await checkRequiredMedia(currentPolicy);
    const { session } = await send({
      type: "DATT_JOIN_EXAM",
      baseUrl: element("backend-url").value,
      joinCode: element("join-code").value,
      studentName,
      candidateId,
    });
    setStatus("join-status", `Đã tạo phiên ${session.sessionId}. Hãy kích hoạt cửa sổ giám sát vừa mở.`, "success");
    element("join-card").classList.add("hidden");
  } catch (error) {
    setStatus("join-status", error.message, "error");
  } finally {
    element("join-exam").disabled = false;
  }
});

async function initialize() {
  const [{ settings }, { session }, extensionInfo] = await Promise.all([
    send({ type: "DATT_GET_SETTINGS" }),
    send({ type: "DATT_GET_ACTIVE" }),
    send({ type: "DATT_GET_EXTENSION_INFO" }),
  ]);
  element("extension-info").textContent =
    `Extension ${extensionInfo.version} · OAuth redirect: ${extensionInfo.oauthRedirectUri}`;
  if (settings?.baseUrl) element("backend-url").value = settings.baseUrl;
  if (session) {
    element("active-card").classList.remove("hidden");
    element("join-card").classList.add("hidden");
    element("active-summary").textContent = `${session.examName} · ${session.studentName} · ${session.connected ? "đã kết nối" : "đang kết nối lại"}`;
  }
}

initialize().catch((error) => setStatus("setup-status", error.message, "error"));
