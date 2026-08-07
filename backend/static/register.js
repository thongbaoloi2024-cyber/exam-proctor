document.getElementById("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const organization_name = document.getElementById("organization_name").value;
  const admin_email = document.getElementById("admin_email").value;
  const admin_password = document.getElementById("admin_password").value;
  const errorEl = document.getElementById("error-message");
  errorEl.hidden = true;

  const response = await fetch("/auth/register", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ organization_name, admin_email, admin_password }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    errorEl.textContent = body.detail || "Khong dang ky duoc - email co the da ton tai.";
    errorEl.hidden = false;
    return;
  }

  const body = await response.json();
  API.setSession(body.role, body.org_id);
  window.location.href = "/ui/organization";
});
