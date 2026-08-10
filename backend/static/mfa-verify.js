const mfaForm = document.getElementById("mfa-verify-form");
const mfaCode = document.getElementById("mfa-login-code");
const mfaError = document.getElementById("mfa-error");
const mfaAttempts = document.getElementById("mfa-attempts");

function destinationFor(body) {
  if (body.mfa_setup_required) return "/ui/mfa";
  if (body.role === "system_admin") return "/ui/system";
  if (body.role === "admin" || body.role === "org_admin") return "/ui/organization";
  return "/ui/exams";
}

function showRemaining(attempts) {
  mfaAttempts.textContent = `Bạn còn ${attempts} lần nhập.`;
  mfaAttempts.classList.toggle("is-critical", attempts <= 1);
}

async function loadChallenge() {
  const response = await fetch("/auth/mfa/challenge", { credentials: "same-origin" });
  if (!response.ok) {
    window.location.replace("/ui/login?error=mfa_expired");
    return;
  }
  const body = await response.json();
  document.getElementById("mfa-account").textContent = `Xác minh cho ${body.email} bằng Authenticator hoặc recovery code.`;
  showRemaining(body.attempts_remaining);
}

document.querySelectorAll("[data-code-type]").forEach((button) => {
  button.addEventListener("click", () => {
    const recovery = button.dataset.codeType === "recovery";
    document.querySelectorAll("[data-code-type]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", String(active));
    });
    document.getElementById("mfa-code-label").firstChild.textContent = recovery
      ? "Recovery code "
      : "Mã xác thực 6 chữ số ";
    mfaCode.inputMode = recovery ? "text" : "numeric";
    mfaCode.maxLength = recovery ? 32 : 6;
    mfaCode.placeholder = recovery ? "Nhập recovery code" : "000000";
    mfaCode.value = "";
    mfaCode.focus();
  });
});

mfaForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  mfaError.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Đang xác minh...";
  try {
    const response = await fetch("/auth/mfa/verify", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: mfaCode.value.trim() }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      mfaError.textContent = body.detail || "Mã xác minh không hợp lệ.";
      mfaError.hidden = false;
      showRemaining(body.attempts_remaining ?? 0);
      mfaCode.value = "";
      if ((body.attempts_remaining ?? 0) === 0) {
        submitButton.disabled = true;
        submitButton.textContent = "Đã hết lượt nhập";
        window.setTimeout(() => window.location.replace("/ui/login?error=mfa_expired"), 1400);
      }
      return;
    }
    API.setSession(body.role, body.org_id);
    window.location.replace(destinationFor(body));
  } catch (_error) {
    mfaError.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    mfaError.hidden = false;
  } finally {
    if (!submitButton.disabled || submitButton.textContent !== "Đã hết lượt nhập") {
      submitButton.disabled = false;
      submitButton.textContent = "Xác minh và tiếp tục";
    }
  }
});

loadChallenge().catch(() => window.location.replace("/ui/login?error=mfa_expired"));
