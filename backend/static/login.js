document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  const errorEl = document.getElementById("error-message");
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  errorEl.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Đang xác thực...";

  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      errorEl.textContent = errorBody.detail || "Sai email hoặc mật khẩu.";
      errorEl.hidden = false;
      return;
    }

    const body = await response.json();
    if (body.mfa_required) {
      window.location.replace("/ui/mfa/verify");
      return;
    }
    API.setSession(body.role, body.org_id);
    window.location.href = body.mfa_setup_required
      ? "/ui/mfa"
      : body.role === "system_admin"
        ? "/ui/system"
        : body.role === "admin" || body.role === "org_admin"
          ? "/ui/organization"
          : "/ui/exams";
  } catch (_error) {
    errorEl.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    errorEl.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Đăng nhập";
  }
});

const loginErrors = {
  google_cancelled: "Bạn đã hủy đăng nhập Google.",
  google_verification_failed: "Không xác minh được tài khoản Google. Vui lòng thử lại.",
  google_email_not_verified: "Email Google chưa được xác minh.",
  google_identity_conflict: "Tài khoản Google đang liên kết với một người dùng khác.",
  account_unavailable: "Tài khoản hoặc tổ chức hiện không hoạt động.",
  mfa_expired: "Phiên xác minh đã hết hạn hoặc đã hết lượt nhập. Vui lòng đăng nhập lại.",
};
const loginError = new URLSearchParams(window.location.search).get("error");
if (loginError && loginErrors[loginError]) {
  const errorEl = document.getElementById("error-message");
  errorEl.textContent = loginErrors[loginError];
  errorEl.hidden = false;
}

document.querySelectorAll('.google-button[aria-disabled="true"]').forEach((button) => {
  button.addEventListener("click", (event) => event.preventDefault());
});
