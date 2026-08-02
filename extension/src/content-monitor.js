(function installExamContentMonitor() {
  "use strict";

  if (globalThis.__DATT_CONTENT_MONITOR__) return;
  globalThis.__DATT_CONTENT_MONITOR__ = true;

  const ext = globalThis.browser || globalThis.chrome;
  let policy = null;
  let hiddenAt = null;
  let bannerHost = null;

  function emit(eventType, details = {}) {
    ext.runtime.sendMessage({ type: "DATT_CONTENT_EVENT", eventType, details }).catch(() => {});
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
    if (policy.examOrigin && location.origin !== policy.examOrigin) {
      emit("NAVIGATION_AWAY", { observedOrigin: location.origin });
    }
    showFullscreenBanner();
    emit("CONTENT_MONITOR_READY", { observedOrigin: location.origin });
    sendResponse?.({ ok: true });
    return true;
  });
})();
