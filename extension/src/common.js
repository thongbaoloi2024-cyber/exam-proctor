(function attachDattCommon(root) {
  "use strict";

  const VERSION = "1.0.0";

  function normalizeBaseUrl(raw) {
    const url = new URL(String(raw || "").trim());
    if (!['http:', 'https:'].includes(url.protocol) || !url.host || url.username || url.password) {
      throw new Error("Địa chỉ backend phải là URL HTTP(S) hợp lệ.");
    }
    const localHosts = new Set(["localhost", "127.0.0.1", "[::1]"]);
    if (url.protocol !== "https:" && !localHosts.has(url.hostname)) {
      throw new Error("Backend từ xa bắt buộc dùng HTTPS.");
    }
    url.pathname = url.pathname.replace(/\/+$/, "");
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  }

  function wsBaseUrl(httpBase) {
    const url = new URL(normalizeBaseUrl(httpBase));
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString().replace(/\/$/, "");
  }

  function originPattern(raw) {
    const url = new URL(raw);
    return `${url.origin}/*`;
  }

  function safeOrigin(raw) {
    try {
      const url = new URL(raw);
      return ['http:', 'https:'].includes(url.protocol) ? url.origin : null;
    } catch (_error) {
      return null;
    }
  }

  function parseVersion(value) {
    const match = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$/.exec(String(value));
    if (!match) throw new Error("Phiên bản không đúng định dạng MAJOR.MINOR.PATCH.");
    return match.slice(1, 4).map(Number);
  }

  function compareVersions(left, right) {
    const a = parseVersion(left);
    const b = parseVersion(right);
    for (let index = 0; index < 3; index += 1) {
      if (a[index] !== b[index]) return a[index] < b[index] ? -1 : 1;
    }
    return 0;
  }

  function browserInfo(userAgent = root.navigator?.userAgent || "") {
    const candidates = [
      ["Firefox", /Firefox\/(\d+(?:\.\d+)*)/],
      ["Edge", /Edg\/(\d+(?:\.\d+)*)/],
      ["Chrome", /Chrome\/(\d+(?:\.\d+)*)/],
    ];
    for (const [name, pattern] of candidates) {
      const match = pattern.exec(userAgent);
      if (match) return { name, version: match[1] };
    }
    return { name: "Unknown", version: null };
  }

  function randomId(prefix = "evt") {
    const uuid = root.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    return `${prefix}-${uuid}`.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 64);
  }

  function parseOAuthRedirect(rawUrl) {
    const url = new URL(rawUrl);
    return {
      grant: url.searchParams.get("grant"),
      error: url.searchParams.get("error"),
    };
  }

  async function apiRequest(baseUrl, path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.json !== undefined) headers["Content-Type"] = "application/json";
    if (options.bearerToken) headers.Authorization = `Bearer ${options.bearerToken}`;
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.json === undefined ? undefined : JSON.stringify(options.json),
      cache: "no-store",
      redirect: options.redirect || "follow",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const error = new Error(body.detail || `Backend trả về HTTP ${response.status}.`);
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    return response.json();
  }

  root.DATT = Object.freeze({
    VERSION,
    normalizeBaseUrl,
    wsBaseUrl,
    originPattern,
    safeOrigin,
    compareVersions,
    browserInfo,
    randomId,
    parseOAuthRedirect,
    apiRequest,
  });
})(globalThis);
