# Báo cáo Tuần 15 — Hoàn thiện multi-tenant + bảo mật cơ bản

> Viết cho người dùng đọc lại. Bối cảnh: Tuần 12-14 đã xây xong backend, Client↔Backend integration, và dashboard giám thị (xem `docs/BAO_CAO_TUAN14.md`, `docs/KE_HOACH_PLATFORM.md`). Tuần này rà soát lại tính đúng đắn multi-tenant và bảo mật trước khi chuyển sang giai đoạn đánh giá/luận văn (Tuần 16+).

---

## 1. Mục tiêu tuần này

Trước khi coi phần platform là "xong", cần chứng minh bằng test tự động (không chỉ tin vào thiết kế) rằng: (1) dữ liệu của 1 trường/trung tâm khảo thí không thể bị trường khác xem trộm, và (2) hệ thống chịu được nhiều thí sinh thi cùng lúc mà không lỗi.

## 2. Đã làm gì

### 2.1. Kiểm tra cách ly dữ liệu giữa các tổ chức (multi-tenant isolation)

Từ Tuần 12, mọi API đã được thiết kế để chỉ cho phép 1 tổ chức xem dữ liệu của chính mình — nhưng trước tuần này, việc đó mới chỉ được test cho 1 API (danh sách kỳ thi). Tuần này viết thêm test cho **toàn bộ** các API còn lại có dữ liệu riêng theo tổ chức:

- Xem danh sách thí sinh đang thi của 1 kỳ thi
- Kết thúc hộ 1 phiên thi
- Tải báo cáo PDF/HTML của 1 phiên
- Xem ảnh chụp bằng chứng
- Kết nối vào dashboard real-time

Với cả 5 chỗ trên, thử tạo 2 tổ chức khác nhau (giả vờ là "kẻ tấn công" ở tổ chức B cố xem dữ liệu của tổ chức A) — **kết quả: bị chặn đúng ở cả 5 chỗ**, kể cả khi kẻ tấn công có vai trò giám thị (không chỉ admin).

**Kết luận: hệ thống ĐÃ cách ly đúng từ trước — tuần này chỉ là viết bằng chứng test tự động để đảm bảo về sau không ai vô tình làm hỏng tính năng này mà không biết.**

### 2.2. Kiểm tra chống giả mạo token đăng nhập

Hệ thống có 2 loại "vé vào cửa" (token) khác nhau: 1 loại cho admin/giám thị (đăng nhập bằng email/mật khẩu), 1 loại cho thí sinh (chỉ cần mã tham gia, không cần tài khoản). Đã viết test xác nhận: **không thể lấy vé của thí sinh để giả làm giám thị, và ngược lại** — kể cả khi thử dùng token "linh tinh" không hợp lệ.

### 2.3. Script kiểm tra nhiều thí sinh thi đồng thời

Viết `scripts/simulate_concurrent_students.py` — script tự động giả lập nhiều thí sinh (mặc định 3) cùng gửi dữ liệu giám sát cùng lúc tới hệ thống thật (không phải giả lập trong bộ nhớ), để bạn có thể tự kiểm tra dashboard hoạt động ổn định trước khi demo thật trước hội đồng, mà không cần nhiều máy tính/webcam.

**Đã tự chạy thử thành công**: khởi động server thật, chạy script với 3 "thí sinh giả" gửi dữ liệu liên tục trong 30 giây — dashboard nhận đúng và đầy đủ toàn bộ cập nhật real-time từ cả 3 người, không có lỗi nào trong log server.

Cách bạn tự chạy lại:
```bash
docker compose up --build
python scripts/simulate_concurrent_students.py --num-students 3 --duration-sec 30
```
Script sẽ in ra tài khoản đăng nhập + đường dẫn dashboard để bạn mở trình duyệt xem trực tiếp.

### 2.4. Tài liệu

- `README.md`: thêm mục "Bảo mật" (lưu ý khóa bí mật JWT trong file cấu hình Docker chỉ dùng cho demo, cần đổi trước khi triển khai thật) và hướng dẫn dùng script mô phỏng nhiều phiên.
- `docker-compose.yml`: thêm ghi chú cảnh báo ngay tại dòng cấu hình khóa bí mật.

## 3. Kết quả kiểm thử

- **9 test bảo mật mới** (5 test cách ly tổ chức + 3 test chống giả mạo token + 1 test token rác) — **pass hết ngay từ lần chạy đầu tiên**.
- Tổng cộng dự án hiện có **229 test tự động**, không test nào bị hỏng.
- Đã tự chạy `docker compose`-tương-đương (uvicorn thật) và script mô phỏng nhiều phiên — xác nhận hoạt động đúng ngoài phạm vi test giả lập.

## 4. Có tìm thấy lỗi bảo mật nào không?

**Không** — cả 9 test bảo mật mới đều pass ngay từ đầu, nghĩa là thiết kế cách ly/token từ Tuần 12 vốn đã làm đúng. Đây là kết quả tốt, không phải "chưa kiểm nên chưa biết" — giờ đã có bằng chứng test tự động xác nhận, và sẽ tự động phát hiện nếu sau này có ai đó vô tình sửa code làm hỏng tính năng này.

## 5. Còn thiếu (chưa làm, ngoài phạm vi tuần này)

- Đóng gói client (`main.py`) thành file `.exe` chạy được không cần cài Python (đã bàn với bạn trước đó — để dành làm sau nếu cần, hoặc chỉ ghi vào luận văn như hướng phát triển).
- Chưa deploy backend lên cloud thật (theo đúng lựa chọn ban đầu: chỉ demo bằng Docker Compose cục bộ).

---

**Tiếp theo**: Tuần 16 — Quay & gán nhãn bộ test (bắt đầu giai đoạn đánh giá định lượng, xem `KE_HOACH_4_THANG_THEO_TUAN.md`).
