"use strict";

const ext = globalThis.browser || globalThis.chrome;
let session = null;
let cameraStream = null;
let displayStream = null;

function element(id) { return document.getElementById(id); }

async function send(message) {
  const response = await ext.runtime.sendMessage(message);
  if (!response?.ok) throw new Error(response?.error || "Extension không phản hồi.");
  return response;
}

function setStatus(text, kind = "") {
  const node = element("monitor-status");
  node.textContent = text;
  node.className = `status${kind ? ` ${kind}` : ""}`;
}

function renderIndicator(label, ok) {
  const pill = document.createElement("span");
  pill.className = `pill ${ok ? "indicator-ok" : "indicator-wait"}`;
  pill.textContent = label;
  return pill;
}

function render() {
  if (!session) return;
  const rows = [
    ["Kỳ thi", session.examName],
    ["Thí sinh", session.studentName],
    ["Xác thực", session.authenticationMethod === "google" ? "Google" : "Họ tên + mã thí sinh"],
    ["Kết nối", session.connected ? "Đã kết nối" : "Đang kết nối lại"],
  ];
  element("monitor-meta").replaceChildren(...rows.map(([label, value]) => {
    const row = document.createElement("div");
    const bold = document.createElement("b");
    bold.textContent = `${label}: `;
    row.append(bold, document.createTextNode(value || "-"));
    return row;
  }));
  element("indicators").replaceChildren(
    renderIndicator("Camera", !session.policy.require_camera || Boolean(cameraStream)),
    renderIndicator("Microphone", !session.policy.require_microphone || Boolean(cameraStream?.getAudioTracks().length)),
    renderIndicator("Chia sẻ màn hình", !session.policy.require_screen_share || Boolean(displayStream)),
  );
}

function monitorTrack(track, mutedType, endedType) {
  track.addEventListener("mute", () => send({
    type: "DATT_MONITOR_EVENT", eventType: mutedType, details: {},
  }).catch(() => {}));
  track.addEventListener("ended", () => send({
    type: "DATT_MONITOR_EVENT", eventType: endedType, details: {},
  }).catch(() => {}));
}

async function startMonitoring() {
  if (!session) throw new Error("Không tìm thấy phiên thi.");
  element("start-monitoring").disabled = true;
  setStatus("Đang xin quyền thiết bị...");
  try {
    if (session.policy.require_screen_share) {
      displayStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      const displayTrack = displayStream.getVideoTracks()[0];
      const surface = displayTrack?.getSettings?.().displaySurface;
      if (surface && surface !== "monitor") {
        displayStream.getTracks().forEach((track) => track.stop());
        displayStream = null;
        throw new Error("Hãy chọn toàn bộ màn hình, không chọn riêng tab hoặc cửa sổ.");
      }
      monitorTrack(displayTrack, "SCREEN_SHARE_ENDED", "SCREEN_SHARE_ENDED");
    }

    if (session.policy.require_camera || session.policy.require_microphone) {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: Boolean(session.policy.require_camera),
        audio: Boolean(session.policy.require_microphone),
      });
      element("camera-preview").srcObject = cameraStream;
      cameraStream.getVideoTracks().forEach((track) => monitorTrack(track, "CAMERA_MUTED", "CAMERA_ENDED"));
      cameraStream.getAudioTracks().forEach((track) => monitorTrack(track, "MICROPHONE_MUTED", "MICROPHONE_ENDED"));
    }

    await send({ type: "DATT_MEDIA_READY" });
    session.mediaReady = true;
    render();
    setStatus("Giám sát đã bật. Chuyển sang trang bài thi để bắt đầu.", "success");
  } catch (error) {
    await send({
      type: "DATT_MONITOR_EVENT",
      eventType: "PERMISSION_MISSING",
      details: { metadata: { component: "required_media" } },
    }).catch(() => {});
    setStatus(error.message || "Không thể bật thiết bị bắt buộc.", "error");
    element("start-monitoring").disabled = false;
  }
}

function stopTracks() {
  cameraStream?.getTracks().forEach((track) => track.stop());
  displayStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  displayStream = null;
}

element("start-monitoring").addEventListener("click", () => startMonitoring());
element("end-session").addEventListener("click", async () => {
  element("end-session").disabled = true;
  setStatus("Đang kết thúc phiên...");
  try {
    await send({ type: "DATT_END_SESSION", reason: "completed" });
    stopTracks();
    setStatus("Phiên đã kết thúc.", "success");
    setTimeout(() => window.close(), 500);
  } catch (error) {
    setStatus(error.message, "error");
    element("end-session").disabled = false;
  }
});

async function initialize() {
  const response = await send({ type: "DATT_GET_ACTIVE" });
  session = response.session;
  if (!session) {
    setStatus("Không có phiên thi đang hoạt động.", "error");
    element("start-monitoring").disabled = true;
    element("end-session").disabled = true;
    return;
  }
  render();
  setStatus("Nhấn “Kích hoạt giám sát” và cấp các quyền được yêu cầu.");
}

window.addEventListener("unload", stopTracks);
initialize().catch((error) => setStatus(error.message, "error"));
