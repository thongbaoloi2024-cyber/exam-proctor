"use strict";

if (!globalThis.DATT && typeof importScripts === "function") {
  importScripts("common.js");
}

const ext = globalThis.browser || globalThis.chrome;
const ACTIVE_KEY = "dattActiveSession";
const DEVICE_KEY = "dattDeviceId";
const CANDIDATE_KEY = "dattCandidateAuth";
const SETTINGS_KEY = "dattSettings";
const KEEPALIVE_MS = 15_000;
const MAX_PENDING_EVENTS = 200;

let active = null;
let socket = null;
let connecting = false;
let keepaliveTimer = null;
let reconnectTimer = null;
let eventFlushTimer = null;
let reconnectAttempt = 0;
let sentEventIds = new Set();

function sessionStorageArea() {
  if (!ext.storage.session) {
    throw new Error("Trình duyệt không hỗ trợ storage.session; hãy nâng cấp trình duyệt.");
  }
  return ext.storage.session;
}

async function restrictSensitiveStorage() {
  for (const area of [ext.storage.local, ext.storage.session].filter(Boolean)) {
    try {
      if (typeof area.setAccessLevel === "function") {
        await area.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" });
      }
    } catch (_error) {
      // Older Firefox builds do not expose setAccessLevel. Content scripts in
      // this extension never call storage APIs, so no token is messaged to them.
    }
  }
}

async function ensureDeviceId() {
  const stored = await ext.storage.local.get(DEVICE_KEY);
  if (stored[DEVICE_KEY]) return stored[DEVICE_KEY];
  const deviceId = crypto.randomUUID();
  await ext.storage.local.set({ [DEVICE_KEY]: deviceId });
  return deviceId;
}

async function persistActive() {
  if (active) await sessionStorageArea().set({ [ACTIVE_KEY]: active });
  else await sessionStorageArea().remove(ACTIVE_KEY);
}

function publicActive() {
  if (!active) return null;
  return {
    sessionId: active.sessionId,
    examName: active.examName,
    studentName: active.studentName,
    candidateId: active.candidateId,
    authenticationMethod: active.authenticationMethod,
    policy: active.policy,
    connected: socket?.readyState === WebSocket.OPEN,
    examTabId: active.examTabId || null,
    monitorWindowId: active.monitorWindowId || null,
  };
}

async function requestOriginPermissions(urls) {
  const origins = [...new Set(urls.filter(Boolean).map(DATT.originPattern))];
  if (!origins.length) return true;
  const contains = await ext.permissions.contains({ origins });
  if (contains) return true;
  return ext.permissions.request({ origins });
}

async function technicalDataAllowed() {
  const isFirefox = ext.runtime.getURL("/").startsWith("moz-extension://");
  if (!isFirefox) return true;
  try {
    const permissions = await ext.permissions.getAll();
    return Array.isArray(permissions.data_collection)
      && permissions.data_collection.includes("technicalAndInteraction");
  } catch (_error) {
    return false;
  }
}

async function loadCandidateAuth() {
  const stored = await ext.storage.local.get(CANDIDATE_KEY);
  return stored[CANDIDATE_KEY] || null;
}

async function candidateState(baseUrl) {
  const auth = await loadCandidateAuth();
  if (!auth || auth.baseUrl !== DATT.normalizeBaseUrl(baseUrl)) return null;
  if (Date.parse(auth.expiresAt) <= Date.now()) {
    await ext.storage.local.remove(CANDIDATE_KEY);
    return null;
  }
  try {
    const profile = await DATT.apiRequest(baseUrl, "/candidate-auth/me", {
      bearerToken: auth.token,
    });
    auth.profile = profile;
    await ext.storage.local.set({ [CANDIDATE_KEY]: auth });
    return profile;
  } catch (error) {
    if (error.status === 401) await ext.storage.local.remove(CANDIDATE_KEY);
    return null;
  }
}

async function googleLogin(baseUrl) {
  const normalizedBase = DATT.normalizeBaseUrl(baseUrl);
  const deviceId = await ensureDeviceId();
  const extensionRedirect = ext.identity.getRedirectURL("google");
  const startUrl = `${normalizedBase}/candidate-auth/google/start?extension_redirect_uri=${encodeURIComponent(extensionRedirect)}`;
  const finalUrl = await ext.identity.launchWebAuthFlow({ url: startUrl, interactive: true });
  if (!finalUrl) throw new Error("Không nhận được kết quả đăng nhập Google.");
  const result = DATT.parseOAuthRedirect(finalUrl);
  if (result.error) throw new Error(`Đăng nhập Google không hoàn tất: ${result.error}`);
  if (!result.grant) throw new Error("Backend không trả về grant đăng nhập.");

  const login = await DATT.apiRequest(normalizedBase, "/candidate-auth/google/complete", {
    method: "POST",
    json: { grant: result.grant, device_id: deviceId },
  });
  const stored = {
    baseUrl: normalizedBase,
    token: login.candidate_token,
    expiresAt: login.token_expires_at,
    profile: login.profile,
  };
  await ext.storage.local.set({ [CANDIDATE_KEY]: stored });
  return login.profile;
}

async function googleLogout(baseUrl) {
  const auth = await loadCandidateAuth();
  try {
    if (auth && auth.baseUrl === DATT.normalizeBaseUrl(baseUrl)) {
      await DATT.apiRequest(baseUrl, "/candidate-auth/logout", {
        method: "POST",
        bearerToken: auth.token,
      });
    }
  } finally {
    await ext.storage.local.remove(CANDIDATE_KEY);
  }
}

async function getPolicy(baseUrl, joinCode) {
  const normalizedBase = DATT.normalizeBaseUrl(baseUrl);
  const policy = await DATT.apiRequest(
    normalizedBase,
    `/exams/join-policy/${encodeURIComponent(String(joinCode).trim().toUpperCase())}`,
  );
  await ext.storage.local.set({ [SETTINGS_KEY]: { baseUrl: normalizedBase } });
  return policy;
}

async function joinExam(message) {
  if (active) throw new Error("Đã có một phiên thi đang hoạt động.");
  const baseUrl = DATT.normalizeBaseUrl(message.baseUrl);
  const joinCode = String(message.joinCode || "").trim().toUpperCase();
  const policy = await getPolicy(baseUrl, joinCode);
  if (DATT.compareVersions(DATT.VERSION, policy.min_extension_version) < 0) {
    throw new Error(`Cần extension phiên bản ${policy.min_extension_version} trở lên.`);
  }
  if (!(await requestOriginPermissions([baseUrl, policy.exam_url]))) {
    throw new Error("Bạn chưa cấp quyền truy cập backend hoặc trang bài thi cho extension.");
  }

  const deviceId = await ensureDeviceId();
  const info = DATT.browserInfo();
  const mayTransmitTechnical = await technicalDataAllowed();
  const reportedInfo = mayTransmitTechnical
    ? info
    : { name: "Browser", version: null };
  const payload = {
    join_code: joinCode,
    student_name: policy.candidate_auth_mode === "manual" ? message.studentName : null,
    candidate_id: policy.candidate_auth_mode === "manual" ? message.candidateId : null,
    client_info: {
      client_type: "browser_extension",
      extension_version: DATT.VERSION,
      browser_name: reportedInfo.name,
      device_id: deviceId,
    },
  };
  let candidateToken = null;
  if (policy.candidate_auth_mode === "google") {
    const candidateAuth = await loadCandidateAuth();
    if (!candidateAuth || candidateAuth.baseUrl !== baseUrl) {
      throw new Error("Hãy đăng nhập Google trước khi tham gia.");
    }
    candidateToken = candidateAuth.token;
  }

  const joined = await DATT.apiRequest(baseUrl, "/exams/join", {
    method: "POST",
    json: payload,
    bearerToken: candidateToken,
  });
  active = {
    baseUrl,
    wsBaseUrl: DATT.wsBaseUrl(baseUrl),
    sessionId: joined.session_id,
    sessionToken: joined.session_token,
    examName: joined.exam_name,
    studentName: joined.student_name,
    candidateId: joined.candidate_id,
    authenticationMethod: joined.authentication_method,
    policy,
    deviceId,
    browserInfo: reportedInfo,
    mayTransmitTechnical,
    nextSequence: 0,
    pendingEvents: [],
    examTabId: null,
    examWindowId: null,
    monitorTabId: null,
    monitorWindowId: null,
    mediaReady: false,
    bootstrapping: true,
  };
  await persistActive();
  await connectSocket();
  await openExamAndMonitor();
  return publicActive();
}

async function openExamAndMonitor() {
  if (!active) return;
  if (active.policy.exam_url && !active.examTabId) {
    const examTab = await ext.tabs.create({ url: active.policy.exam_url, active: false });
    active.examTabId = examTab.id;
    active.examWindowId = examTab.windowId;
    await persistActive();
  }
  if (!active.monitorWindowId) {
    const monitorWindow = await ext.windows.create({
      url: ext.runtime.getURL("monitor.html"),
      type: "popup",
      width: 420,
      height: 690,
      focused: true,
    });
    active.monitorWindowId = monitorWindow.id;
    active.monitorTabId = monitorWindow.tabs?.[0]?.id || null;
  }
  active.bootstrapping = false;
  await persistActive();
}

async function activateExamTab() {
  if (!active?.examTabId) return;
  await ext.tabs.update(active.examTabId, { active: true });
  if (active.examWindowId != null) await ext.windows.update(active.examWindowId, { focused: true });
  await configureExamContent(active.examTabId);
}

async function configureExamContent(tabId) {
  if (!active || tabId !== active.examTabId) return;
  try {
    await ext.scripting.executeScript({ target: { tabId }, files: ["common.js", "content-monitor.js"] });
    await ext.tabs.sendMessage(tabId, {
      type: "DATT_CONFIGURE",
      policy: {
        examOrigin: DATT.safeOrigin(active.policy.exam_url),
        requireFullscreen: active.policy.require_fullscreen,
        blockClipboard: active.policy.block_clipboard,
      },
    });
  } catch (_error) {
    await enqueueBrowserEvent("PERMISSION_MISSING", {
      metadata: { component: "content_monitor" },
    });
  }
}

async function getWsTicket() {
  return DATT.apiRequest(active.baseUrl, `/sessions/${encodeURIComponent(active.sessionId)}/ws-ticket`, {
    method: "POST",
    bearerToken: active.sessionToken,
  });
}

async function connectSocket() {
  if (!active || connecting || socket?.readyState === WebSocket.OPEN) return;
  connecting = true;
  try {
    const ticket = await getWsTicket();
    const ws = new WebSocket(`${active.wsBaseUrl}/ws/client`, [
      ticket.subprotocol,
      `ticket.${ticket.ticket}`,
    ]);
    socket = ws;
    sentEventIds = new Set();
    ws.onopen = () => {
      reconnectAttempt = 0;
      ws.send(JSON.stringify({
        type: "client_hello",
        data: {
          extension_version: DATT.VERSION,
          browser_name: active.browserInfo.name,
          browser_version: active.browserInfo.version,
          platform: active.mayTransmitTechnical ? (navigator.platform || null) : null,
          device_id: active.deviceId,
          capabilities: active.mayTransmitTechnical ? [
            "camera",
            "microphone",
            "screen_share",
            "content_monitor",
            "storage_session",
          ] : [],
        },
      }));
      clearInterval(keepaliveTimer);
      keepaliveTimer = setInterval(sendHeartbeat, KEEPALIVE_MS);
      flushPendingEvents();
    };
    ws.onmessage = (event) => handleSocketMessage(event.data);
    ws.onerror = () => {};
    ws.onclose = () => {
      if (socket === ws) socket = null;
      clearInterval(keepaliveTimer);
      keepaliveTimer = null;
      clearTimeout(eventFlushTimer);
      eventFlushTimer = null;
      if (active) scheduleReconnect();
    };
  } catch (error) {
    if (error.status === 409) {
      await clearActive();
      throw error;
    }
    scheduleReconnect();
  } finally {
    connecting = false;
  }
}

function sendHeartbeat() {
  if (socket?.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({
    type: "heartbeat",
    data: { timestamp: Date.now() / 1000 },
  }));
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  const delay = Math.min(15_000, 1000 * (2 ** reconnectAttempt));
  reconnectAttempt = Math.min(reconnectAttempt + 1, 4);
  reconnectTimer = setTimeout(() => connectSocket(), delay);
}

async function handleSocketMessage(raw) {
  let message;
  try {
    message = JSON.parse(raw);
  } catch (_error) {
    return;
  }
  if (message.type === "browser_event_ack" && message.data?.event_id && active) {
    active.pendingEvents = active.pendingEvents.filter(
      (item) => item.data.event_id !== message.data.event_id,
    );
    sentEventIds.delete(message.data.event_id);
    await persistActive();
  }
}

async function enqueueBrowserEvent(eventType, details = {}) {
  if (!active) return;
  const event = {
    type: "browser_event",
    data: {
      event_id: DATT.randomId("browser"),
      sequence: active.nextSequence,
      event_type: eventType,
      client_timestamp: new Date().toISOString(),
      observed_origin: DATT.safeOrigin(details.observedOrigin),
      duration_ms: Number.isFinite(details.durationMs) ? Math.max(0, Math.round(details.durationMs)) : null,
      metadata: details.metadata || {},
    },
  };
  active.nextSequence += 1;
  if (active.pendingEvents.length >= MAX_PENDING_EVENTS) {
    const lowPriorityIndex = active.pendingEvents.findIndex((item) => [
      "CONTENT_MONITOR_READY", "TAB_VISIBLE", "WINDOW_FOCUS", "FULLSCREEN_ENTER",
    ].includes(item.data.event_type));
    active.pendingEvents.splice(lowPriorityIndex >= 0 ? lowPriorityIndex : 0, 1);
  }
  active.pendingEvents.push(event);
  await persistActive();
  flushPendingEvents();
}

function flushPendingEvents() {
  if (!active || socket?.readyState !== WebSocket.OPEN || eventFlushTimer) return;
  const sendNext = () => {
    eventFlushTimer = null;
    if (!active || socket?.readyState !== WebSocket.OPEN) return;
    const event = active.pendingEvents.find((item) => !sentEventIds.has(item.data.event_id));
    if (!event) return;
    socket.send(JSON.stringify(event));
    sentEventIds.add(event.data.event_id);
    // Keep comfortably below the backend's 10 messages/second limit, even
    // during reconnect when a persisted queue must be replayed.
    eventFlushTimer = setTimeout(sendNext, 250);
  };
  sendNext();
}

async function endSession(reason = "completed") {
  if (!active) return;
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "end_session", data: { reason } }));
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  await clearActive();
}

async function clearActive() {
  clearTimeout(reconnectTimer);
  clearInterval(keepaliveTimer);
  clearTimeout(eventFlushTimer);
  reconnectTimer = null;
  keepaliveTimer = null;
  eventFlushTimer = null;
  if (socket) {
    try { socket.close(1000, "session ended"); } catch (_error) {}
  }
  socket = null;
  active = null;
  await persistActive();
}

async function handleMessage(message, sender) {
  switch (message?.type) {
    case "DATT_PREPARE_PERMISSIONS":
      return { granted: await requestOriginPermissions(message.urls || []) };
    case "DATT_GET_SETTINGS": {
      const stored = await ext.storage.local.get(SETTINGS_KEY);
      return { settings: stored[SETTINGS_KEY] || { baseUrl: "http://localhost:8000" } };
    }
    case "DATT_GET_EXTENSION_INFO":
      return {
        version: DATT.VERSION,
        oauthRedirectUri: ext.identity.getRedirectURL("google"),
        origin: new URL(ext.runtime.getURL("/")).origin,
      };
    case "DATT_GET_POLICY":
      return { policy: await getPolicy(message.baseUrl, message.joinCode) };
    case "DATT_GET_CANDIDATE":
      return { profile: await candidateState(message.baseUrl) };
    case "DATT_GOOGLE_LOGIN":
      return { profile: await googleLogin(message.baseUrl) };
    case "DATT_GOOGLE_LOGOUT":
      await googleLogout(message.baseUrl);
      return { profile: null };
    case "DATT_JOIN_EXAM":
      return { session: await joinExam(message) };
    case "DATT_GET_ACTIVE":
      return { session: publicActive() };
    case "DATT_MEDIA_READY":
      if (active) {
        active.mediaReady = true;
        await persistActive();
        await activateExamTab();
      }
      return { session: publicActive() };
    case "DATT_MONITOR_EVENT":
      await enqueueBrowserEvent(message.eventType, message.details || {});
      return { accepted: true };
    case "DATT_CONTENT_EVENT":
      if (!active || sender.tab?.id !== active.examTabId) return { accepted: false };
      await enqueueBrowserEvent(message.eventType, message.details || {});
      return { accepted: true };
    case "DATT_END_SESSION":
      await endSession(message.reason || "completed");
      return { ended: true };
    default:
      return { ignored: true };
  }
}

ext.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender)
    .then((result) => sendResponse({ ok: true, ...result }))
    .catch((error) => sendResponse({ ok: false, error: error.message || String(error), status: error.status || 0 }));
  return true;
});

ext.action.onClicked.addListener(() => {
  ext.tabs.create({ url: ext.runtime.getURL("setup.html") });
});

ext.tabs.onActivated.addListener((info) => {
  if (!active || active.bootstrapping || !active.mediaReady || info.tabId === active.examTabId || info.tabId === active.monitorTabId) return;
  ext.tabs.get(info.tabId).then((tab) => enqueueBrowserEvent("TAB_SWITCHED", {
    observedOrigin: tab.url,
  })).catch(() => enqueueBrowserEvent("TAB_SWITCHED"));
});

ext.tabs.onCreated.addListener((tab) => {
  if (!active || active.bootstrapping || !active.mediaReady || tab.id === active.examTabId || tab.id === active.monitorTabId) return;
  enqueueBrowserEvent("NEW_TAB", { observedOrigin: tab.url });
});

ext.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!active || tabId !== active.examTabId) return;
  if (changeInfo.url) {
    const expected = DATT.safeOrigin(active.policy.exam_url);
    const observed = DATT.safeOrigin(changeInfo.url);
    if (expected && observed !== expected) {
      enqueueBrowserEvent("NAVIGATION_AWAY", { observedOrigin: changeInfo.url });
    }
  }
  if (changeInfo.status === "complete") configureExamContent(tabId);
});

ext.tabs.onRemoved.addListener((tabId) => {
  if (!active) return;
  if (tabId === active.examTabId) enqueueBrowserEvent("NAVIGATION_AWAY", {
    metadata: { reason: "exam_tab_closed" },
  });
});

ext.windows.onFocusChanged.addListener((windowId) => {
  if (!active || !active.mediaReady) return;
  if (windowId === active.examWindowId) enqueueBrowserEvent("WINDOW_FOCUS");
  else if (windowId !== active.monitorWindowId) enqueueBrowserEvent("WINDOW_BLUR");
});

ext.windows.onRemoved.addListener((windowId) => {
  if (active && windowId === active.monitorWindowId) {
    enqueueBrowserEvent("MONITOR_CLOSED");
  }
});

ext.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "datt-health" && active && socket?.readyState !== WebSocket.OPEN) connectSocket();
});

async function initialize() {
  await restrictSensitiveStorage();
  await ensureDeviceId();
  const stored = await sessionStorageArea().get(ACTIVE_KEY);
  active = stored[ACTIVE_KEY] || null;
  await ext.alarms.create("datt-health", { periodInMinutes: 1 });
  if (active) {
    connectSocket();
    if (active.bootstrapping) openExamAndMonitor();
  }
}

initialize().catch(() => {});
