# Gói extension dựng sẵn

- `datt-exam-guard-chrome-1.0.0.zip`: tải lên hệ thống quản lý Chrome hoặc
  giải nén rồi chọn **Load unpacked** tại `chrome://extensions` để kiểm thử.
- `datt-exam-guard-firefox-1.0.0-unsigned.zip`: bản chưa ký để kiểm thử nội bộ.
  Trước khi triển khai chính thức cần ký qua Mozilla Add-ons hoặc phân phối
  bằng chính sách quản trị doanh nghiệp.

Source dùng chung nằm trong thư mục `../extension/`; chạy `npm run build` để
tạo lại hai thư mục `extension/dist/chrome` và `extension/dist/firefox`.

Không cấu hình Google OAuth client secret trong extension. Secret chỉ được đặt
ở backend; redirect URI chính xác do trang thiết lập extension hiển thị phải
được đưa vào allowlist của backend và Google Cloud Console.
