document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  const mfaCode = document.getElementById("mfa-code").value.trim();
  const errorEl = document.getElementById("error-message");
  errorEl.hidden = true;

  const response = await fetch("/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, mfa_code: mfaCode || null }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    errorEl.textContent = errorBody.detail || "Sai email hoặc mật khẩu.";
    errorEl.hidden = false;
    return;
  }

  const body = await response.json();
  API.setSession(body.role, body.org_id);
  window.location.href = body.mfa_setup_required
    ? "/ui/mfa"
    : body.role === "system_admin"
      ? "/ui/system"
      : body.role === "admin" || body.role === "org_admin"
        ? "/ui/organization"
        : "/ui/exams";
});
