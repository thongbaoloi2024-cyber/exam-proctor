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
        : isOrganizationAdmin ? "/ui/organization/overview" : "/ui/exams/overview";
      sidebarHomeLink.setAttribute(
        "aria-label",
        `Giám Thị Số - ${
          isSystemAdmin
            ? "Tổng quan hệ thống"
            : isOrganizationAdmin ? "Tổng quan tổ chức" : "Tổng quan kỳ thi"
        }`,
      );
    }
    const brandContext = document.getElementById("sidebar-brand-context");
    if (brandContext) {
      brandContext.textContent = isSystemAdmin
        ? "Trung tâm điều hành"
        : isOrganizationAdmin ? "Quản trị tổ chức" : "Không gian kỳ thi";
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
    if (accountEmail) {
      accountEmail.textContent = this.currentUser?.display_name || this.currentUser?.email || "";
      accountEmail.title = this.currentUser?.email || "";
    }
    const accountAvatar = document.getElementById("account-avatar");
    if (accountAvatar) {
      const accountName = this.currentUser?.display_name
        || (this.currentUser?.email || "user").split("@")[0];
      accountAvatar.textContent = accountName.replace(/[^a-zA-Z0-9À-ỹ]/g, "").slice(0, 2).toUpperCase() || "SA";
      const avatarUrl = this.currentUser?.avatar_url || "";
      const imageRequest = String(Number(accountAvatar.dataset.imageRequest || "0") + 1);
      accountAvatar.dataset.imageRequest = imageRequest;
      accountAvatar.style.backgroundImage = "";
      accountAvatar.classList.remove("has-image");
      if (avatarUrl) {
        const image = new Image();
        image.addEventListener("load", () => {
          if (accountAvatar.dataset.imageRequest !== imageRequest) return;
          accountAvatar.style.backgroundImage = `url(${JSON.stringify(avatarUrl)})`;
          accountAvatar.classList.add("has-image");
        });
        image.addEventListener("error", () => {
          if (accountAvatar.dataset.imageRequest !== imageRequest) return;
          accountAvatar.style.backgroundImage = "";
          accountAvatar.classList.remove("has-image");
        });
        image.src = avatarUrl;
      }
    }
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.style.display = this.currentUser ? "" : "none";
    const navOrganization = document.getElementById("nav-organization");
    const navOrganizationSettings = document.getElementById("nav-organization-settings");
    const organizationNavSection = document.getElementById("organization-nav-section");
    const canReadOrganization = !isSystemAdmin && this.hasCapability("org.members.read");
    if (navOrganization) {
      navOrganization.classList.toggle("hidden", !canReadOrganization);
    }
    navOrganizationSettings?.classList.toggle(
      "hidden",
      !this.hasCapability("org.policy.manage"),
    );
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
    document.getElementById("account-settings-button")?.classList.toggle(
      "active",
      window.location.pathname.replace(/\/$/, "") === "/ui/settings",
    );
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
      await this.loadPinnedExams();
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
          ? "/ui/organization/overview"
          : "/ui/exams/overview";
        window.location.replace(destination);
      }
    }, { once: true });
  },

  pinnedExamsStorageKey() {
    const userId = this.currentUser?.id || this.currentUser?.email || "anonymous";
    const organizationId = this.currentUser?.active_org_id || this.currentUser?.org_id || "none";
    return `pinned-exams-expanded:${userId}:${organizationId}`;
  },

  setPinnedExamsExpanded(expanded, persist = true) {
    const list = document.getElementById("pinned-exams-list");
    const toggle = document.getElementById("pinned-exams-toggle");
    if (!list || !toggle) return;
    list.classList.toggle("hidden", !expanded);
    toggle.classList.toggle("expanded", expanded);
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.setAttribute(
      "aria-label",
      expanded ? "Thu gọn danh sách kỳ thi đã ghim" : "Mở danh sách kỳ thi đã ghim",
    );
    if (persist) sessionStorage.setItem(this.pinnedExamsStorageKey(), String(expanded));
  },

  bindPinnedExamsToggle() {
    const toggle = document.getElementById("pinned-exams-toggle");
    if (!toggle || toggle.dataset.bound === "true") return;
    toggle.dataset.bound = "true";
    toggle.addEventListener("click", () => {
      this.setPinnedExamsExpanded(toggle.getAttribute("aria-expanded") !== "true");
    });
  },

  pinnedExamItem(exam) {
    const item = document.createElement("div");
    item.className = "pinned-exam-item";
    const link = document.createElement("a");
    link.href = `/ui/exams/${encodeURIComponent(exam.id)}/detail`;
    link.className = "pinned-exam-link";
    link.title = exam.name;
    const marker = document.createElement("span");
    marker.className = `pinned-exam-status status-${exam.status}`;
    marker.setAttribute("aria-hidden", "true");
    const name = document.createElement("span");
    name.textContent = exam.name;
    link.append(marker, name);
    const unpin = document.createElement("button");
    unpin.type = "button";
    unpin.className = "pinned-exam-unpin";
    unpin.title = `Bỏ ghim ${exam.name}`;
    unpin.setAttribute("aria-label", `Bỏ ghim ${exam.name}`);
    unpin.textContent = "📌";
    unpin.addEventListener("click", async () => {
      unpin.disabled = true;
      try {
        await this.setExamPinned(exam.id, false);
        showToast(`Đã bỏ ghim “${exam.name}”.`, "success");
      } catch (error) {
        unpin.disabled = false;
        showToast(error.message || "Không bỏ ghim được kỳ thi.", "error");
      }
    });
    item.append(link, unpin);
    return item;
  },

  async loadPinnedExams({ forceOpen = false } = {}) {
    const list = document.getElementById("pinned-exams-list");
    if (!list || !this.currentUser) return [];
    this.bindPinnedExamsToggle();
    const canUsePinnedExams = !this.currentUser.is_system_admin
      && (this.getRole() === "exam_manager" || this.getRole() === "proctor")
      && (this.hasCapability("exam.read") || this.hasCapability("exam.create"));
    if (!canUsePinnedExams) {
      list.replaceChildren();
      this.setPinnedExamsExpanded(false, false);
      return [];
    }
    const response = await this.request("/exams/pinned");
    if (!response.ok) return [];
    const exams = await response.json();
    if (exams.length) {
      list.replaceChildren(...exams.map((exam) => this.pinnedExamItem(exam)));
    } else {
      const empty = document.createElement("span");
      empty.className = "pinned-exams-empty";
      empty.textContent = "Chưa có kỳ thi được ghim";
      list.replaceChildren(empty);
    }
    const stored = sessionStorage.getItem(this.pinnedExamsStorageKey());
    const expanded = forceOpen || (stored == null ? exams.length > 0 : stored === "true");
    this.setPinnedExamsExpanded(expanded, forceOpen || stored == null);
    this.updateActiveNavigation();
    return exams;
  },

  async setExamPinned(examId, isPinned) {
    const response = await this.request(`/exams/${encodeURIComponent(examId)}/pin`, {
      method: "PATCH",
      body: JSON.stringify({ is_pinned: isPinned }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Không cập nhật được ghim kỳ thi.");
    await this.loadPinnedExams({ forceOpen: isPinned });
    document.dispatchEvent(new CustomEvent("exam-pin-changed", { detail: body }));
    return body;
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

function apiErrorMessage(payload, fallback) {
  const detail = payload?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === "string" ? item : item?.msg))
      .filter((item) => typeof item === "string" && item.trim());
    if (messages.length) return messages.join(" · ");
  }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return fallback;
}

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
  const footerYear = document.getElementById("page-footer-year");
  if (footerYear) footerYear.textContent = String(new Date().getFullYear());
  API.updateAuthUi();
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) logoutBtn.addEventListener("click", () => API.logout());
});
