const organizationForm = document.getElementById("google-organization-form");
const organizationError = document.getElementById("error-message");

async function loadGoogleRegistration() {
  const response = await fetch("/auth/google/registration", { credentials: "same-origin" });
  if (!response.ok) {
    window.location.replace("/ui/register?error=google_verification_failed");
    return;
  }
  const profile = await response.json();
  const name = profile.display_name || profile.email;
  document.getElementById("google-profile-name").textContent = name;
  document.getElementById("google-profile-email").textContent = profile.email;
  document.getElementById("google-profile-avatar").textContent = name.slice(0, 1).toUpperCase();
}

organizationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  organizationError.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Đang hoàn tất...";
  try {
    const response = await fetch("/auth/google/register/complete", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        organization_name: document.getElementById("google-organization-name").value,
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      organizationError.textContent = body.detail || "Không thể hoàn tất đăng ký.";
      organizationError.hidden = false;
      return;
    }
    API.setSession(body.role, body.org_id);
    window.location.replace("/ui/organization");
  } catch (_error) {
    organizationError.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
    organizationError.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Hoàn tất đăng ký";
  }
});

loadGoogleRegistration().catch(() => window.location.replace("/ui/register"));
