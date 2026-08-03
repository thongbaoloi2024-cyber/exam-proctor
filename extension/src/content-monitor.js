(function installExamContentMonitor() {
  "use strict";

  if (globalThis.__DATT_CONTENT_MONITOR__) return;
  globalThis.__DATT_CONTENT_MONITOR__ = true;

  const ext = globalThis.browser || globalThis.chrome;
  let policy = null;
  let session = null;
  let hiddenAt = null;
  let bannerHost = null;
  let monitorHost = null;
  let monitorShadow = null;
  let cameraStream = null;
  let displayStream = null;
  let monitorReady = false;

  function emit(eventType, details = {}) {
    ext.runtime.sendMessage({ type: "DATT_CONTENT_EVENT", eventType, details }).catch(() => {});
  }

  async function send(message) {
    const response = await ext.runtime.sendMessage(message);
    if (!response?.ok) throw new Error(response?.error || "Extension không phản hồi.");
    return response;
  }

  function removeBanner() {
    bannerHost?.remove();
    bannerHost = null;
  }

  function showFullscreenBanner() {
    if (!policy?.requireFullscreen || document.fullscreenElement || bannerHost) return;
    bannerHost = document.createElement("div");
    bannerHost.id = "datt-fullscreen-control";
    const shadow = bannerHost.attachShadow({ mode: "closed" });
    const wrapper = document.createElement("div");
    wrapper.style.cssText = [
      "position:fixed", "inset:0 0 auto 0", "z-index:2147483647",
      "padding:10px 14px", "background:#7f1d1d", "color:#fff",
      "font:600 14px system-ui,sans-serif", "display:flex",
      "align-items:center", "justify-content:center", "gap:12px",
      "box-shadow:0 2px 12px rgba(0,0,0,.35)",
    ].join(";");
    const text = document.createElement("span");
    text.textContent = "Kỳ thi yêu cầu toàn màn hình.";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Vào toàn màn hình";
    button.style.cssText = "border:0;border-radius:6px;padding:7px 12px;background:#fff;color:#7f1d1d;font-weight:700;cursor:pointer";
    button.addEventListener("click", async () => {
      try {
        await document.documentElement.requestFullscreen({ navigationUI: "hide" });
      } catch (_error) {
        emit("PERMISSION_MISSING", { metadata: { component: "fullscreen" } });
      }
    });
    wrapper.append(text, button);
    shadow.appendChild(wrapper);
    document.documentElement.appendChild(bannerHost);
  }

  function stopTracks() {
    cameraStream?.getTracks().forEach((track) => track.stop());
    displayStream?.getTracks().forEach((track) => track.stop());
    cameraStream = null;
    displayStream = null;
  }

  function monitorTrack(track, mutedType, endedType) {
    if (!track) return;
    track.addEventListener("mute", () => {
      send({ type: "DATT_MONITOR_EVENT", eventType: mutedType, details: {} }).catch(() => {});
    });
    track.addEventListener("ended", () => {
      send({ type: "DATT_MONITOR_EVENT", eventType: endedType, details: {} }).catch(() => {});
    });
  }

  function monitorElement(id) {
    return monitorShadow?.getElementById(id);
  }

  function setMonitorStatus(text, kind = "") {
    const node = monitorElement("datt-monitor-status");
    if (!node) return;
    node.textContent = text;
    node.className = `status${kind ? ` ${kind}` : ""}`;
  }

  function renderIndicator(label, ok) {
    const pill = document.createElement("span");
    pill.className = `pill ${ok ? "indicator-ok" : "indicator-wait"}`;
    pill.textContent = label;
    return pill;
  }

  function renderMonitor() {
    if (!monitorShadow || !session) return;
    const meta = monitorElement("datt-monitor-meta");
    const indicators = monitorElement("datt-monitor-indicators");
    const video = monitorElement("datt-camera-preview");
    const rows = [
      ["Kỳ thi", session.examName],
      ["Thí sinh", session.studentName],
      ["Xác thực", session.authenticationMethod === "google" ? "Google" : "Họ tên + mã thí sinh"],
      ["Kết nối", session.connected ? "Đã kết nối" : "Đang kết nối lại"],
    ];
    meta.replaceChildren(...rows.map(([label, value]) => {
      const row = document.createElement("div");
      const bold = document.createElement("b");
      bold.textContent = `${label}: `;
      row.append(bold, document.createTextNode(value || "-"));
      return row;
    }));
    indicators.replaceChildren(
      renderIndicator("Camera", !session.policy.require_camera || Boolean(cameraStream)),
      renderIndicator("Microphone", !session.policy.require_microphone || Boolean(cameraStream?.getAudioTracks().length)),
      renderIndicator("Chia sẻ màn hình", !session.policy.require_screen_share || Boolean(displayStream)),
    );
    if (video && cameraStream && video.srcObject !== cameraStream) {
      video.srcObject = cameraStream;
    }
  }

  function hideMonitorPanel() {
    monitorElement("datt-monitor-backdrop")?.classList.add("hidden");
    monitorElement("datt-monitor-launcher")?.classList.remove("hidden");
  }

  function showMonitorPanel() {
    monitorElement("datt-monitor-backdrop")?.classList.remove("hidden");
    monitorElement("datt-monitor-launcher")?.classList.add("hidden");
  }

  async function startMonitoring() {
    if (!session) throw new Error("Không tìm thấy phiên thi.");
    const startButton = monitorElement("datt-start-monitoring");
    startButton.disabled = true;
    setMonitorStatus("Đang xin quyền thiết bị...");
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
        monitorElement("datt-camera-preview").srcObject = cameraStream;
        cameraStream.getVideoTracks().forEach((track) => monitorTrack(track, "CAMERA_MUTED", "CAMERA_ENDED"));
        cameraStream.getAudioTracks().forEach((track) => monitorTrack(track, "MICROPHONE_MUTED", "MICROPHONE_ENDED"));
      }

      const response = await send({ type: "DATT_MEDIA_READY" });
      session = response.session || session;
      monitorReady = true;
      renderMonitor();
      setMonitorStatus("Giám sát đã bật. Bảng sẽ thu nhỏ để bạn làm bài.", "success");
      setTimeout(hideMonitorPanel, 900);
    } catch (error) {
      await send({
        type: "DATT_MONITOR_EVENT",
        eventType: "PERMISSION_MISSING",
        details: { metadata: { component: "required_media" } },
      }).catch(() => {});
      setMonitorStatus(error.message || "Không thể bật thiết bị bắt buộc.", "error");
      startButton.disabled = false;
    }
  }

  function showMonitorOverlay(nextSession) {
    session = nextSession || session;
    if (!session) return;
    if (!monitorHost) {
      monitorHost = document.createElement("div");
      monitorHost.id = "datt-monitor-overlay";
      monitorShadow = monitorHost.attachShadow({ mode: "open" });
      monitorShadow.innerHTML = `
        <style>
          :host { all: initial; color-scheme: dark; }
          *, *::before, *::after { box-sizing: border-box; }
          .backdrop {
            position: fixed;
            inset: 0;
            z-index: 2147483647;
            display: grid;
            place-items: center;
            padding: 20px;
            background: rgba(5, 8, 13, .58);
            backdrop-filter: blur(3px);
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          }
          .panel {
            width: min(440px, 100%);
            max-height: min(720px, calc(100vh - 40px));
            overflow: auto;
            border: 1px solid #303746;
            border-radius: 8px;
            background: #181c24;
            color: #edf0f5;
            box-shadow: 0 24px 80px rgba(0, 0, 0, .42);
          }
          .header {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 16px 16px 10px;
          }
          .brand-mark {
            width: 34px;
            height: 34px;
            border-radius: 8px;
            display: grid;
            place-items: center;
            flex: 0 0 auto;
            background: #1d4ed8;
            color: #fff;
            font-weight: 800;
            font-size: 14px;
          }
          h2 { margin: 0; font-size: 18px; line-height: 1.2; letter-spacing: 0; }
          .muted { color: #a7afbd; font-size: 13px; line-height: 1.42; }
          .body { padding: 0 16px 16px; }
          .section {
            border: 1px solid #303746;
            border-radius: 8px;
            padding: 13px;
            margin-top: 12px;
            background: #11151c;
          }
          .monitor-meta { display: grid; gap: 5px; font-size: 13px; line-height: 1.35; }
          .monitor-meta b { color: #edf0f5; }
          .indicator-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
          .pill {
            display: inline-block;
            border-radius: 999px;
            border: 1px solid #303746;
            padding: 3px 9px;
            color: #a7afbd;
            font-size: 12px;
            line-height: 1.3;
          }
          .indicator-ok { border-color: #28a745; color: #70d98a; }
          .indicator-wait { border-color: #c98b22; color: #f0bd5c; }
          video {
            display: block;
            width: 100%;
            max-height: 260px;
            margin-top: 12px;
            background: #050608;
            border: 1px solid #303746;
            border-radius: 8px;
            object-fit: cover;
            transform: scaleX(-1);
          }
          .actions { display: flex; flex-wrap: wrap; gap: 9px; align-items: center; margin-top: 12px; }
          button {
            border: 0;
            border-radius: 7px;
            padding: 10px 14px;
            background: #4f8ef7;
            color: white;
            font: 600 13px system-ui, sans-serif;
            cursor: pointer;
          }
          button.danger { background: #dc4c4c; }
          button.secondary { background: #374151; }
          button:disabled { opacity: .55; cursor: not-allowed; }
          .status { min-height: 20px; margin: 10px 0 0; color: #a7afbd; font-size: 13px; line-height: 1.35; }
          .status.error { color: #ff8585; }
          .status.success { color: #70d98a; }
          .launcher {
            position: fixed;
            right: 16px;
            bottom: 16px;
            z-index: 2147483647;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border: 1px solid #303746;
            box-shadow: 0 10px 30px rgba(0, 0, 0, .35);
          }
          .hidden { display: none !important; }
          @media (max-width: 520px) {
            .backdrop { padding: 12px; align-items: start; }
            .panel { max-height: calc(100vh - 24px); }
            .header { padding: 14px 14px 8px; }
            .body { padding: 0 14px 14px; }
          }
        </style>
        <div id="datt-monitor-backdrop" class="backdrop" role="dialog" aria-modal="true" aria-labelledby="datt-monitor-title">
          <div class="panel">
            <div class="header">
              <div class="brand-mark">GS</div>
              <div>
                <h2 id="datt-monitor-title">Kích hoạt giám sát</h2>
                <div class="muted">Bật các quyền bắt buộc trước khi bắt đầu làm bài</div>
              </div>
            </div>
            <div class="body">
              <section class="section">
                <div id="datt-monitor-meta" class="monitor-meta"></div>
                <div id="datt-monitor-indicators" class="indicator-row"></div>
              </section>
              <section class="section">
                <video id="datt-camera-preview" autoplay muted playsinline></video>
                <p class="muted">Extension không truyền video liên tục lên server.</p>
                <div class="actions">
                  <button id="datt-start-monitoring" type="button">Kích hoạt giám sát</button>
                  <button id="datt-hide-monitor" type="button" class="secondary">Thu nhỏ</button>
                  <button id="datt-end-session" type="button" class="danger">Kết thúc phiên</button>
                </div>
                <p id="datt-monitor-status" class="status" role="status" aria-live="polite"></p>
              </section>
            </div>
          </div>
        </div>
        <button id="datt-monitor-launcher" type="button" class="launcher hidden">Giám sát đang bật</button>
      `;
      monitorElement("datt-start-monitoring").addEventListener("click", () => startMonitoring());
      monitorElement("datt-hide-monitor").addEventListener("click", () => {
        if (!monitorReady) {
          setMonitorStatus("Hãy kích hoạt giám sát trước khi thu nhỏ.", "error");
          return;
        }
        hideMonitorPanel();
      });
      monitorElement("datt-monitor-launcher").addEventListener("click", showMonitorPanel);
      monitorElement("datt-end-session").addEventListener("click", async () => {
        const button = monitorElement("datt-end-session");
        button.disabled = true;
        setMonitorStatus("Đang kết thúc phiên...");
        try {
          await send({ type: "DATT_END_SESSION", reason: "completed" });
          stopTracks();
          monitorReady = false;
          setMonitorStatus("Phiên đã kết thúc.", "success");
          setTimeout(() => {
            monitorHost?.remove();
            monitorHost = null;
            monitorShadow = null;
          }, 500);
        } catch (error) {
          setMonitorStatus(error.message, "error");
          button.disabled = false;
        }
      });
      document.documentElement.appendChild(monitorHost);
    }
    renderMonitor();
    showMonitorPanel();
    setMonitorStatus("Nhấn “Kích hoạt giám sát” và cấp các quyền được yêu cầu.");
  }

  document.addEventListener("visibilitychange", () => {
    if (!policy) return;
    if (document.hidden) {
      hiddenAt = performance.now();
      emit("TAB_HIDDEN", { observedOrigin: location.origin });
    } else {
      const durationMs = hiddenAt == null ? null : performance.now() - hiddenAt;
      hiddenAt = null;
      emit("TAB_VISIBLE", { observedOrigin: location.origin, durationMs });
    }
  }, true);

  document.addEventListener("fullscreenchange", () => {
    if (!policy?.requireFullscreen) return;
    if (document.fullscreenElement) {
      removeBanner();
      emit("FULLSCREEN_ENTER", { observedOrigin: location.origin });
    } else {
      emit("FULLSCREEN_EXIT", { observedOrigin: location.origin });
      showFullscreenBanner();
    }
  }, true);

  for (const [domEvent, eventType] of [
    ["copy", "CLIPBOARD_COPY"],
    ["cut", "CLIPBOARD_COPY"],
    ["paste", "CLIPBOARD_PASTE"],
    ["contextmenu", "CONTEXT_MENU"],
  ]) {
    document.addEventListener(domEvent, (event) => {
      if (!policy) return;
      emit(eventType, { observedOrigin: location.origin });
      if (policy.blockClipboard) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
  }

  ext.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "DATT_CONFIGURE") return undefined;
    policy = message.policy;
    session = message.session || session;
    if (policy.examOrigin && location.origin !== policy.examOrigin) {
      emit("NAVIGATION_AWAY", { observedOrigin: location.origin });
    }
    showFullscreenBanner();
    if (message.showMonitor) showMonitorOverlay(message.session);
    emit("CONTENT_MONITOR_READY", { observedOrigin: location.origin });
    sendResponse?.({ ok: true });
    return true;
  });

  window.addEventListener("pagehide", stopTracks);
})();
