/* Global light/dark theme controller. Only the non-sensitive UI preference is
 * persisted; authentication continues to live in the HttpOnly session cookie.
 */
(() => {
  "use strict";

  const STORAGE_KEY = "giam-thi-so-theme";
  const DEFAULT_THEME = "dark";

  function readStoredTheme() {
    try {
      const storedTheme = localStorage.getItem(STORAGE_KEY);
      return storedTheme === "light" || storedTheme === "dark"
        ? storedTheme
        : DEFAULT_THEME;
    } catch (_error) {
      return DEFAULT_THEME;
    }
  }

  function updateToggle(theme) {
    const toggle = document.getElementById("theme-toggle");
    if (!toggle) return;

    const lightThemeActive = theme === "light";
    const label = lightThemeActive
      ? "Chuyển sang giao diện tối"
      : "Chuyển sang giao diện sáng";
    toggle.setAttribute("aria-label", label);
    toggle.setAttribute("title", label);
    toggle.setAttribute("aria-pressed", String(lightThemeActive));
  }

  function applyTheme(theme, persist = false) {
    const nextTheme = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    document.documentElement.style.colorScheme = nextTheme;
    updateToggle(nextTheme);

    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, nextTheme);
      } catch (_error) {
        // The selected theme still applies for this page when storage is blocked.
      }
    }
  }

  function initializeToggle() {
    const toggle = document.getElementById("theme-toggle");
    if (!toggle) return;

    updateToggle(document.documentElement.dataset.theme || DEFAULT_THEME);
    toggle.addEventListener("click", () => {
      const currentTheme = document.documentElement.dataset.theme || DEFAULT_THEME;
      applyTheme(currentTheme === "dark" ? "light" : "dark", true);
    });
  }

  applyTheme(readStoredTheme());
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeToggle, { once: true });
  } else {
    initializeToggle();
  }
})();
