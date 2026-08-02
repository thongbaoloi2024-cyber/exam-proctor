# Báo cáo Tuần 14 — Dashboard giám thị

> **Tài liệu lịch sử của mốc Tuần 14.** Cơ chế `localStorage` và Blob workaround
> mô tả bên dưới đã được thay bằng cookie HttpOnly + DOM an toàn trong bản
> hardening. Xem `README.md`, `SECURITY.md` và source hiện tại.

> Viết cho người dùng đọc lại, tóm tắt những gì đã làm trong phiên làm việc này. Bối cảnh: Tuần 12 (backend skeleton) và Tuần 13 (Client↔Backend integration) đã xong trước đó — xem `docs/KE_HOACH_PLATFORM.md` mục 3/3b. Tuần này xây dashboard web thật cho giám thị, theo đúng lộ trình đã thống nhất trong `KE_HOACH_4_THANG_THEO_TUAN.md`.

---

## 1. Mục tiêu tuần này

Giám thị cần 1 giao diện web thật để: đăng nhập, tạo kỳ thi (lấy mã tham gia phát cho thí sinh), xem bảng điểm rủi ro của nhiều thí sinh **real-time**, và xem chi tiết từng phiên (timeline vi phạm, tải báo cáo). Quyết định kiến trúc đã chốt từ trước: **Jinja2 + vanilla JS, không dùng React** (lý do: giữ toàn bộ kỹ năng dùng trong đồ án là Python, tránh thêm 1 toolchain build mới dưới áp lực thời gian — xem `docs/KE_HOACH_PLATFORM.md` mục 1).

## 2. Đã xây gì

### 2.1. Giao diện (5 trang)

| Trang | Route | Chức năng |
|---|---|---|
| Đăng nhập | `/ui/login` | Admin/giám thị đăng nhập, nhận cookie HttpOnly |
| Đăng ký | `/ui/register` | Tạo tổ chức + tài khoản admin đầu tiên |
| Danh sách kỳ thi | `/ui/exams` | Admin tạo kỳ thi (hiện mã tham gia để phát cho thí sinh), admin tạo thêm tài khoản giám thị |
| Dashboard | `/ui/exams/{id}/dashboard` | Bảng lưới real-time: tên thí sinh + điểm rủi ro + màu trạng thái, cập nhật qua WebSocket |
| Chi tiết phiên | `/ui/exams/{id}/sessions/{id}` | Timeline vi phạm, xem ảnh chụp bằng chứng, tải báo cáo HTML/PDF |

Toàn bộ trang dùng chung `base.html` (khung + CSS) và gọi thẳng API JSON đã có sẵn từ Tuần 12-13 (không viết logic nghiệp vụ mới trong tầng hiển thị — mọi phân quyền/kiểm tra vẫn nằm ở API).

### 2.2. Backend bổ sung

- `GET /sessions/{id}/detail` — trả về thông tin phiên + danh sách vi phạm (sắp xếp theo thời gian) + risk timeline, cho trang chi tiết phiên. Tái dùng thẳng `load_session_report_data()` (đã có từ Tuần 11) thay vì viết lại logic đọc JSONL.
- `GET /sessions/{id}/snapshots/{filename}` — phục vụ ảnh chụp bằng chứng, có chặn path traversal (không cho dùng `../` để đọc file ngoài thư mục phiên).

### 2.3. Hạ tầng phục vụ trang

- `backend/routers/pages.py` — route trả HTML.
- `backend/static/` — 1 file CSS tự viết (không dùng CDN ngoài, để buổi demo bằng Docker Compose không phụ thuộc mạng internet) + JS thuần cho từng trang.

## 3. Một bug thật đã phát hiện và sửa ngay trong lúc code

**Trang `/exams` không bao giờ hiện ra — luôn báo lỗi 401.**

Nguyên nhân: API JSON danh sách kỳ thi (từ Tuần 12) và trang HTML (Tuần 14) tôi định đặt **cùng 1 địa chỉ `/exams`**. Khi 2 route trùng địa chỉ, hệ thống chỉ chạy route nào đăng ký TRƯỚC — mà API JSON (yêu cầu đăng nhập) đăng ký trước trang HTML, nên trình duyệt gọi `/exams` sẽ luôn nhận về lỗi "chưa đăng nhập" thay vì trang web, dù có đăng nhập hay chưa.

**Cách sửa**: tách hẳn địa chỉ các trang web sang tiền tố riêng `/ui/...` (VD `/ui/exams`, `/ui/login`...), giữ nguyên toàn bộ địa chỉ API JSON cũ không đổi gì. Bug này được phát hiện ngay bằng cách tự chạy test, không phải để sót — đã viết thêm test xác nhận cả 2 (trang `/ui/exams` tải được, API `/exams` vẫn yêu cầu đăng nhập như cũ) để nó không tái diễn.

## 4. Một vấn đề thiết kế phát hiện và xử lý

Thiết kế ban đầu từng lưu JWT trong `localStorage` và phải dùng Blob URL để tải
file có xác thực. Bản hardening đã bỏ thiết kế đó: JWT nằm trong cookie HttpOnly
cùng origin, nên trình duyệt tự gửi cookie cho báo cáo/snapshot mà JavaScript
không thể đọc token.

## 5. Kiểm thử đã làm

- **13 test tự động mới** cho phần dashboard (tổng cộng dự án hiện có **220 test tự động**, không có test nào bị hỏng so với trước khi làm Tuần 14).
- **Chạy thử bằng server thật** (không chỉ test giả lập): tự khởi động server, dùng script tự động đóng vai "1 admin + 3 thí sinh" gửi dữ liệu qua mạng thật, xác nhận toàn bộ luồng hoạt động đúng — từ đăng ký, tạo kỳ thi, thí sinh tham gia bằng mã, gửi cảnh báo vi phạm, đến dashboard nhận được cập nhật real-time đúng nội dung.

## 6. Giới hạn — cần bạn tự kiểm tra

Môi trường làm việc này **không có trình duyệt thật**, nên tôi chỉ xác nhận được phần giao diện web hoạt động đúng thông qua kiểm thử tự động + mô phỏng bằng script, **chưa tự mắt nhìn thấy giao diện chạy trong trình duyệt**. Cần bạn:

1. Chạy `docker compose up --build`, mở `http://localhost:8000` bằng trình duyệt thật.
2. Thử đăng ký → đăng nhập → tạo kỳ thi → mở dashboard.
3. Dùng script/thiết bị khác giả lập 1-2 thí sinh join và gửi dữ liệu (hoặc đợi đến khi nối `main.py` thật — đã làm ở Tuần 13) → xác nhận dashboard cập nhật đúng, giao diện không bị vỡ/lỗi hiển thị.
4. Báo lại nếu có bug hiển thị, CSS xấu, hoặc luồng nào bị vướng — đây là loại lỗi chỉ trình duyệt thật mới phát hiện được (giống như trước đây cần webcam thật để phát hiện bug EYE_STATE/MOUTH_STATE).

## 7. Còn thiếu (chưa làm, để dành Tuần 15+)

Theo đúng lộ trình đã thống nhất, Tuần 14 chỉ làm phần dashboard — chưa làm:
- Rà soát bảo mật multi-tenant sâu hơn (cách ly giữa các tổ chức ở MỌI endpoint).
- Đóng gói/README hướng dẫn demo đầy đủ cho hội đồng.
- Demo thử nhiều phiên đồng thời thật (không phải script mô phỏng).

Những việc này thuộc Tuần 15, xem `docs/KE_HOACH_4_THANG_THEO_TUAN.md`.

---

**Tài liệu liên quan**: `docs/KE_HOACH_PLATFORM.md` mục 3c (chi tiết kỹ thuật đầy đủ hơn), `KE_HOACH_4_THANG_THEO_TUAN.md` (lộ trình tổng).
