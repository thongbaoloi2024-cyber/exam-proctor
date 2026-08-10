document.getElementById("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const organization_name = document.getElementById("organization_name").value;
  const admin_email = document.getElementById("admin_email").value;
  const admin_password = document.getElementById("admin_password").value;
  const errorEl = document.getElementById("error-message");
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  errorEl.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Đang tạo tài khoản...";

  try {
    const response = await fetch("/auth/register", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization_name, admin_email, admin_password }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      errorEl.textContent = body.detail || "Không đăng ký được; email có thể đã tồn tại.";
      errorEl.hidden = false;
      return;
    }

    const body = await response.json();
    API.setSession(body.role, body.org_id);
    window.location.href = "/ui/organization";
  } catch (_error) {
    errorEl.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    errorEl.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Tạo tài khoản";
  }
});

const registerErrors = {
  google_cancelled: "Bạn đã hủy đăng ký bằng Google.",
  google_verification_failed: "Không xác minh được tài khoản Google. Vui lòng thử lại.",
  google_email_not_verified: "Email Google chưa được xác minh.",
  google_identity_conflict: "Tài khoản Google đang liên kết với một người dùng khác.",
  account_exists: "Tài khoản đã tồn tại. Hãy chuyển sang trang đăng nhập.",
};
const registerError = new URLSearchParams(window.location.search).get("error");
if (registerError && registerErrors[registerError]) {
  const errorEl = document.getElementById("error-message");
  errorEl.textContent = registerErrors[registerError];
  errorEl.hidden = false;
}

document.querySelectorAll('.google-button[aria-disabled="true"]').forEach((button) => {
  button.addEventListener("click", (event) => event.preventDefault());
});
