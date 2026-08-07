/* Same-origin API helper. Authentication lives in an HttpOnly SameSite
 * cookie; JavaScript never stores or places JWTs in URLs.
 */
const API = {
  currentUser: null,

  getRole() {
    return this.currentUser?.effective_role || this.currentUser?.role || null;
  },

  hasCapability(capability) {
    return Boolean(this.currentUser?.capabilities?.includes(capability));
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
    const role = this.getRole();
    const isAuthenticated = Boolean(this.currentUser);
    const isSystemAdmin = role === "system_admin";
    const isOrganizationAdmin = role === "org_admin" || role === "admin";
    const isExamManager = role === "exam_manager" || role === "proctor";
    document.body.classList.toggle("has-role-sidebar", isAuthenticated);
    document.body.classList.toggle("has-system-sidebar", isSystemAdmin);
    document.body.classList.toggle("has-organization-sidebar", isOrganizationAdmin);
    document.body.classList.toggle("has-exam-manager-sidebar", isExamManager);

    const sidebarHomeLink = document.getElementById("sidebar-home-link");
    if (sidebarHomeLink) {
      sidebarHomeLink.href = isSystemAdmin
        ? "/ui/system"
        : isOrganizationAdmin ? "/ui/organization" : "/ui/exams";
      sidebarHomeLink.setAttribute(
        "aria-label",
        `Giám Thị Số - ${
          isSystemAdmin
            ? "Tổng quan hệ thống"
            : isOrganizationAdmin ? "Quản trị tổ chức" : "Trang kỳ thi"
        }`,
      );
    }
    const brandContext = document.getElementById("sidebar-brand-context");
    if (brandContext) {
      brandContext.textContent = isSystemAdmin
        ? "Control Center"
        : isOrganizationAdmin ? "Organization Console" : "Exam Workspace";
    }
    document.getElementById("system-platform-badge")?.classList.toggle("hidden", !isSystemAdmin);
    document.getElementById("organization-platform-badge")?.classList.toggle(
      "hidden",
      !isOrganizationAdmin,
    );
    document.getElementById("exam-platform-badge")?.classList.toggle("hidden", !isExamManager);

    const roleBadge = document.getElementById("role-badge");
    if (roleBadge) roleBadge.textContent = ROLE_LABEL_VI[this.getRole()] || "";
    const sidebarAccount = document.getElementById("sidebar-account");
    sidebarAccount?.classList.toggle("hidden", !this.currentUser);
    const accountEmail = document.getElementById("account-email");
    if (accountEmail) accountEmail.textContent = this.currentUser?.email || "";
    const accountAvatar = document.getElementById("account-avatar");
    if (accountAvatar) {
      const accountName = (this.currentUser?.email || "user").split("@")[0];
      accountAvatar.textContent = accountName.replace(/[^a-zA-Z0-9]/g, "").slice(0, 2).toUpperCase() || "SA";
    }
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.style.display = this.currentUser ? "" : "none";
    const navOrganization = document.getElementById("nav-organization");
    const organizationNavSection = document.getElementById("organization-nav-section");
    const canReadOrganization = !isSystemAdmin && this.hasCapability("org.members.read");
    if (navOrganization) {
      navOrganization.classList.toggle("hidden", !canReadOrganization);
    }
    organizationNavSection?.classList.toggle("hidden", !canReadOrganization);
    document.getElementById("tenant-nav-group")?.classList.toggle(
      "hidden",
      !isAuthenticated || isSystemAdmin,
    );
    const systemNavGroup = document.getElementById("system-nav-group");
    if (systemNavGroup) {
      systemNavGroup.classList.toggle("hidden", !this.hasCapability("system.organizations.read"));
    }
    const navExams = document.getElementById("nav-exams");
    const canUseExams = !isOrganizationAdmin && (
      this.hasCapability("exam.read") || this.hasCapability("exam.create")
    );
    if (navExams) {
      navExams.classList.toggle("hidden", isSystemAdmin || !canUseExams);
    }
    document.getElementById("exam-nav-section")?.classList.toggle(
      "hidden",
      isSystemAdmin || !canUseExams,
    );
    const navSystemEvidence = document.getElementById("nav-system-evidence");
    if (navSystemEvidence) {
      navSystemEvidence.classList.toggle(
        "hidden",
        !isSystemAdmin || !this.hasCapability("exam.read"),
      );
    }
    document.getElementById("organization-context")?.classList.toggle(
      "hidden",
      !isAuthenticated || isSystemAdmin,
    );
    document.getElementById("system-scope")?.classList.toggle("hidden", !isSystemAdmin);
    this.updateActiveNavigation();
  },

  updateActiveNavigation() {
    const path = window.location.pathname.replace(/\/$/, "") || "/";
    const candidates = Array.from(document.querySelectorAll(".sidebar-nav a[href]"));
    candidates.forEach((item) => {
      item.classList.remove("active");
      item.removeAttribute("aria-current");
    });
    const matching = candidates
      .filter((item) => {
        const href = item.getAttribute("href");
        if (href === "/ui/system") return path === href;
        return path === href || path.startsWith(`${href}/`);
      })
      .sort((left, right) => right.getAttribute("href").length - left.getAttribute("href").length)[0];
    if (matching) {
      matching.classList.add("active");
      matching.setAttribute("aria-current", "page");
    }
  },

  async requireAuth() {
    try {
      const response = await fetch("/auth/me", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("unauthorized");
      this.currentUser = await response.json();
      this.setSession(this.currentUser.role, this.currentUser.org_id);
      this.updateAuthUi();
      await this.loadOrganizationSwitcher();
      return this.currentUser;
    } catch (error) {
      this.clearSession();
      window.location.replace("/ui/login");
      return null;
    }
  },

  async loadOrganizationSwitcher() {
    const select = document.getElementById("organization-switcher");
    if (!select || !this.currentUser) return;
    if (this.getRole() === "system_admin") {
      select.disabled = true;
      return;
    }
    const response = await fetch("/auth/organizations", {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) return;
    const organizations = await response.json();
    select.replaceChildren(...organizations.map((organization) => {
      const option = document.createElement("option");
      option.value = organization.id;
      option.textContent = `${organization.name} · ${ROLE_LABEL_VI[organization.role] || organization.role}`;
      option.selected = organization.id === this.currentUser.active_org_id;
      option.disabled = organization.membership_status !== "active";
      return option;
    }));
    select.disabled = organizations.filter((item) => item.membership_status === "active").length < 2;
    select.addEventListener("change", async () => {
      const switched = await this.request(`/auth/switch-organization/${encodeURIComponent(select.value)}`, {
        method: "POST",
      });
      if (switched.ok) {
        const body = await switched.json();
        const destination = body.role === "admin" || body.role === "org_admin"
          ? "/ui/organization"
          : "/ui/exams";
        window.location.replace(destination);
      }
    }, { once: true });
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

const ROLE_LABEL_VI = {
  admin: "Quản trị viên",
  proctor: "Giám thị",
  system_admin: "Quản trị hệ thống",
  org_admin: "Quản trị tổ chức",
  exam_manager: "Quản lý kỳ thi",
};

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
