function accountInitials(name, email) {
  const source = (name || email?.split("@")[0] || "GT").trim();
  const words = source.split(/\s+/).filter(Boolean);
  return (words.length > 1 ? `${words[0][0]}${words.at(-1)[0]}` : source.slice(0, 2)).toUpperCase();
}

function renderAccountAvatar(url, name, email) {
  const preview = document.getElementById("account-avatar-preview");
  const fallback = document.getElementById("account-avatar-fallback");
  preview.querySelector("img")?.remove();
  fallback.classList.remove("hidden");
  fallback.textContent = accountInitials(name, email);
  const normalizedUrl = (url || "").trim();
  if (!/^https:\/\//i.test(normalizedUrl)) return;
  const image = document.createElement("img");
  image.alt = "Ảnh đại diện";
  image.addEventListener("load", () => {
    if (preview.contains(image)) fallback.classList.add("hidden");
  });
  image.addEventListener("error", () => {
    if (!preview.contains(image)) return;
    image.remove();
    fallback.classList.remove("hidden");
  });
  image.src = normalizedUrl;
  preview.appendChild(image);
}

function populateAccountSettings(user) {
  document.getElementById("settings-display-name").value = user.display_name || "";
  document.getElementById("settings-email").value = user.email || "";
  document.getElementById("settings-phone").value = user.phone || "";
  document.getElementById("settings-avatar-url").value = user.avatar_url || "";
  renderAccountAvatar(user.avatar_url, user.display_name, user.email);
}

function setAccountSettingsReady(ready) {
  document.querySelectorAll("#account-profile-form, #account-password-form").forEach((form) => {
    form.setAttribute("aria-busy", String(!ready));
    form.querySelectorAll("input, button").forEach((control) => {
      control.disabled = !ready;
    });
  });
}

function accountPayload() {
  const phone = document.getElementById("settings-phone").value.trim();
  const avatarUrl = document.getElementById("settings-avatar-url").value.trim();
  return {
    display_name: document.getElementById("settings-display-name").value.trim(),
    email: document.getElementById("settings-email").value.trim(),
    phone: phone || null,
    avatar_url: avatarUrl || null,
  };
}

async function saveAccountProfile(event) {
  event.preventDefault();
  const button = document.getElementById("save-account-profile");
  button.disabled = true;
  try {
    const response = await API.request("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(accountPayload()),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(apiErrorMessage(body, "Không cập nhật được hồ sơ."));
    API.currentUser = body;
    populateAccountSettings(body);
    API.updateAuthUi();
    showToast("Đã cập nhật hồ sơ tài khoản.", "success");
  } catch (error) {
    showToast(error.message || "Không cập nhật được hồ sơ.", "error");
  } finally {
    button.disabled = false;
  }
}

async function changeAccountPassword(event) {
  event.preventDefault();
  const currentPassword = document.getElementById("settings-current-password").value;
  const newPassword = document.getElementById("settings-new-password").value;
  const confirmation = document.getElementById("settings-confirm-password").value;
  if (newPassword !== confirmation) {
    showToast("Xác nhận mật khẩu mới chưa khớp.", "error");
    return;
  }
  const button = document.getElementById("change-account-password");
  button.disabled = true;
  try {
    const response = await API.request("/auth/me/password", {
      method: "PUT",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(apiErrorMessage(body, "Không đổi được mật khẩu."));
    }
    API.clearSession();
    showToast("Đã đổi mật khẩu. Vui lòng đăng nhập lại.", "success");
    setTimeout(() => window.location.replace("/ui/login"), 900);
  } catch (error) {
    button.disabled = false;
    showToast(error.message || "Không đổi được mật khẩu.", "error");
  }
}

async function initializeAccountSettings() {
  const profileForm = document.getElementById("account-profile-form");
  const passwordForm = document.getElementById("account-password-form");
  const avatarInput = document.getElementById("settings-avatar-url");
  const displayNameInput = document.getElementById("settings-display-name");
  const emailInput = document.getElementById("settings-email");
  const refreshPreview = () => {
    renderAccountAvatar(avatarInput.value, displayNameInput.value, emailInput.value);
  };
  profileForm.addEventListener("submit", saveAccountProfile);
  passwordForm.addEventListener("submit", changeAccountPassword);
  avatarInput.addEventListener("input", refreshPreview);
  displayNameInput.addEventListener("input", refreshPreview);
  emailInput.addEventListener("input", refreshPreview);
  setAccountSettingsReady(false);

  const user = await API.requireAuth();
  if (!user) return;
  populateAccountSettings(user);
  setAccountSettingsReady(true);
}

document.addEventListener("DOMContentLoaded", initializeAccountSettings);
