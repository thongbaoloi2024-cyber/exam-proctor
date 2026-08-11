function organizationInitials(name) {
  const words = (name || "TC").trim().split(/\s+/).filter(Boolean);
  return (words.length > 1 ? `${words[0][0]}${words.at(-1)[0]}` : (words[0] || "TC").slice(0, 2)).toUpperCase();
}

function renderOrganizationLogo(url, name) {
  const preview = document.getElementById("organization-logo-preview");
  const fallback = document.getElementById("organization-logo-fallback");
  preview.querySelector("img")?.remove();
  fallback.classList.remove("hidden");
  fallback.textContent = organizationInitials(name);
  const normalizedUrl = (url || "").trim();
  if (!/^https:\/\//i.test(normalizedUrl)) return;
  const image = document.createElement("img");
  image.alt = "Logo tổ chức";
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

function populateOrganizationSettings(organization) {
  document.getElementById("settings-organization-name").value = organization.name || "";
  document.getElementById("settings-organization-logo").value = organization.logo_url || "";
  document.getElementById("settings-organization-address").value = organization.address || "";
  document.getElementById("settings-organization-email").value = organization.email || "";
  document.getElementById("settings-organization-phone").value = organization.phone || "";
  document.getElementById("settings-organization-website").value = organization.website || "";
  renderOrganizationLogo(organization.logo_url, organization.name);
}

function setOrganizationSettingsReady(ready) {
  const form = document.getElementById("organization-profile-form");
  form.setAttribute("aria-busy", String(!ready));
  form.querySelectorAll("input, textarea, button").forEach((control) => {
    control.disabled = !ready;
  });
}

function organizationPayload() {
  const optionalValue = (id) => document.getElementById(id).value.trim() || null;
  return {
    name: document.getElementById("settings-organization-name").value.trim(),
    logo_url: optionalValue("settings-organization-logo"),
    address: optionalValue("settings-organization-address"),
    email: optionalValue("settings-organization-email"),
    phone: optionalValue("settings-organization-phone"),
    website: optionalValue("settings-organization-website"),
  };
}

async function saveOrganizationSettings(event) {
  event.preventDefault();
  const button = document.getElementById("save-organization-profile");
  button.disabled = true;
  try {
    const response = await API.request("/organizations/current", {
      method: "PATCH",
      body: JSON.stringify(organizationPayload()),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(apiErrorMessage(body, "Không cập nhật được tổ chức."));
    populateOrganizationSettings(body);
    const title = document.getElementById("sidebar-brand-title");
    if (title) {
      title.textContent = body.name;
      title.title = body.name;
    }
    showToast("Đã cập nhật thông tin tổ chức.", "success");
  } catch (error) {
    showToast(error.message || "Không cập nhật được tổ chức.", "error");
  } finally {
    button.disabled = false;
  }
}

async function initializeOrganizationSettings() {
  const form = document.getElementById("organization-profile-form");
  const logoInput = document.getElementById("settings-organization-logo");
  const nameInput = document.getElementById("settings-organization-name");
  const refreshPreview = () => renderOrganizationLogo(logoInput.value, nameInput.value);
  form.addEventListener("submit", saveOrganizationSettings);
  logoInput.addEventListener("input", refreshPreview);
  nameInput.addEventListener("input", refreshPreview);
  setOrganizationSettingsReady(false);

  const user = await API.requireAuth();
  if (!user) return;
  if (!API.hasCapability("org.policy.manage")) {
    showToast("Bạn không có quyền cập nhật thông tin tổ chức.", "error");
    window.location.replace("/ui/exams/overview");
    return;
  }
  const response = await API.request("/organizations/current");
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    showToast(apiErrorMessage(body, "Không tải được thông tin tổ chức."), "error");
    return;
  }
  const organization = await response.json();
  populateOrganizationSettings(organization);
  setOrganizationSettingsReady(true);
}

document.addEventListener("DOMContentLoaded", initializeOrganizationSettings);
