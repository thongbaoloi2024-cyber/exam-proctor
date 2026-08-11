let platformPolicyVersion = 0;

function policyValue(id, value) {
  const element = document.getElementById(id);
  if (element.type === "checkbox") element.checked = Boolean(value);
  else element.value = value;
}

async function loadPlatformPolicy() {
  const data = await SystemUI.fetchJson("/system/policy");
  platformPolicyVersion = data.version;
  const policy = data.policy;
  policyValue("system-min-extension", policy.min_extension_version);
  policyValue("system-max-focus", policy.max_focus_loss_seconds);
  policyValue("system-min-retention", policy.min_retention_days);
  policyValue("system-max-retention", policy.max_retention_days);
  ["require_extension", "require_fullscreen", "require_camera", "require_microphone", "require_screen_share", "block_clipboard"].forEach((key) => {
    policyValue(`system-${key.replaceAll("_", "-")}`, policy[key]);
  });
  document.getElementById("system-policy-meta").textContent = `Version ${data.version}${data.updated_at ? ` · cập nhật ${new Date(data.updated_at).toLocaleString("vi-VN")}` : " · giá trị mặc định"}`;
}

document.getElementById("system-policy-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const bool = (id) => document.getElementById(id).checked;
  const payload = {
    expected_version: platformPolicyVersion,
    reason: document.getElementById("system-policy-reason").value,
    policy: {
      min_extension_version: document.getElementById("system-min-extension").value,
      max_focus_loss_seconds: Number(document.getElementById("system-max-focus").value),
      min_retention_days: Number(document.getElementById("system-min-retention").value),
      max_retention_days: Number(document.getElementById("system-max-retention").value),
      require_extension: bool("system-require-extension"),
      require_fullscreen: bool("system-require-fullscreen"),
      require_camera: bool("system-require-camera"),
      require_microphone: bool("system-require-microphone"),
      require_screen_share: bool("system-require-screen-share"),
      block_clipboard: bool("system-block-clipboard"),
    },
  };
  const response = await API.request("/system/policy", { method: "PUT", body: JSON.stringify(payload) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return showToast(body.detail?.message || body.detail || "Không lưu được chính sách.", "error");
  document.getElementById("system-policy-reason").value = "";
  showToast("Đã cập nhật security floor.", "success");
  await loadPlatformPolicy();
});

async function initializeSystemPolicy() {
  const user = await SystemUI.initialize();
  if (!user) return;
  await loadPlatformPolicy();
}
initializeSystemPolicy().catch((error) => showToast(error.message, "error"));
