/* Same-origin API helper. Authentication lives in an HttpOnly SameSite
 * cookie; JavaScript never stores or places JWTs in URLs.
 */
const API = {
  currentUser: null,

  getRole() {
    return this.currentUser?.role || sessionStorage.getItem("role");
  },

  setSession(role, orgId) {
    if (role) sessionStorage.setItem("role", role);
    if (orgId) sessionStorage.setItem("org_id", orgId);
  },

  clearSession() {
    this.currentUser = null;
    sessionStorage.removeItem("role");
    sessionStorage.removeItem("org_id");
  },

  updateAuthUi() {
    const roleBadge = document.getElementById("role-badge");
    if (roleBadge) roleBadge.textContent = ROLE_LABEL_VI[this.getRole()] || "";
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.style.display = this.currentUser ? "inline-block" : "none";
  },

  async requireAuth() {
    try {
      const response = await fetch("/auth/me", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("unauthorized");
      this.currentUser = await response.json();
      this.setSession(this.currentUser.role, this.currentUser.org_id);
      this.updateAuthUi();
      return this.currentUser;
    } catch (error) {
      this.clearSession();
      window.location.replace("/ui/login");
      return null;
    }
  },

  async request(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(path, Object.assign(
      { credentials: "same-origin", cache: "no-store" }, options, { headers },
    ));
    if (response.status === 401) {
      this.clearSession();
      window.location.replace("/ui/login");
      throw new Error("Chua dang nhap hoac phien da het han.");
    }
    return response;
  },

  async logout() {
    try {
      await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      this.clearSession();
      window.location.replace("/ui/login");
    }
  },
};

async function openAuthenticatedFile(url) {
  const response = await API.request(url);
  if (!response.ok) {
    showToast("Khong tai duoc file (co the chua co du lieu).", "error");
    return;
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  window.open(objectUrl, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

const ROLE_LABEL_VI = { admin: "Quản trị viên", proctor: "Giám thị" };

function showToast(message, type = "info") {
  const region = document.getElementById("toast-region");
  if (!region) {
    alert(message);
    return;
  }
  const toast = document.createElement("div");
  toast.className = `toast${type === "success" ? " toast-success" : type === "error" ? " toast-error" : ""}`;
  toast.textContent = String(message);
  region.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

document.addEventListener("DOMContentLoaded", () => {
  API.updateAuthUi();
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) logoutBtn.addEventListener("click", () => API.logout());
});
