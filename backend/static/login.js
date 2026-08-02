document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  const errorEl = document.getElementById("error-message");
  errorEl.hidden = true;

  const response = await fetch("/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    errorEl.textContent = "Sai email hoac mat khau.";
    errorEl.hidden = false;
    return;
  }

  const body = await response.json();
  API.setSession(body.role, body.org_id);
  window.location.href = "/ui/exams";
});
