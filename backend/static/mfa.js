document.getElementById("mfa-start").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const status = document.getElementById("mfa-status");
  button.disabled = true;
  status.textContent = "Đang tạo mã QR…";
  try {
    const response = await API.request("/auth/mfa/setup", { method: "POST" });
    if (!response.ok) {
      showToast("Không khởi tạo được MFA.", "error");
      status.textContent = "Không tạo được mã QR. Vui lòng thử lại.";
      return;
    }
    const data = await response.json();
    if (!data.qr_code_data_url || !data.qr_code_data_url.startsWith("data:image/png;base64,")) {
      showToast("Dữ liệu mã QR không hợp lệ.", "error");
      status.textContent = "Máy chủ không trả về ảnh QR hợp lệ.";
      return;
    }
    document.getElementById("mfa-qr").src = data.qr_code_data_url;
    document.getElementById("mfa-secret").textContent = data.secret;
    document.getElementById("mfa-uri").href = data.provisioning_uri;
    document.getElementById("mfa-recovery").textContent = data.recovery_codes.join("\n");
    document.getElementById("mfa-setup-data").classList.remove("hidden");
    status.textContent = "Mã QR đã sẵn sàng để quét.";
    button.textContent = "Tạo lại mã QR";
  } catch (_error) {
    showToast("Không kết nối được máy chủ.", "error");
    status.textContent = "Không kết nối được máy chủ. Vui lòng thử lại.";
  } finally {
    button.disabled = false;
  }
});

document.getElementById("mfa-confirm-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await API.request("/auth/mfa/confirm", {
    method: "POST",
    body: JSON.stringify({ code: document.getElementById("mfa-confirm-code").value }),
  });
  if (!response.ok) {
    showToast("Mã MFA không hợp lệ.", "error");
    return;
  }
  window.location.replace("/ui/system");
});

API.requireAuth();
