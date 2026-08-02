# Kế hoạch thiết kế lại giao diện — hướng "sản phẩm thương mại"

> Viết sau khi hoàn thiện dashboard MVP (Tuần 14-15 + đợt polish gần nhất — xem `docs/BAO_CAO_TUAN14.md`, `docs/KE_HOACH_PLATFORM.md` mục 3c).

## ✅ Mức A — Đã làm xong

Quyết định: tên thương hiệu **"Giám Thị Số"**, chỉ làm Mức A (không làm Mức B lúc này).

Đã triển khai đủ 5 việc ở mục 6:
1. **Thương hiệu**: tên "Giám Thị Số" + logo SVG (icon mắt đơn giản) áp dụng nhất quán ở sidebar, tiêu đề mọi trang, trang đăng nhập/đăng ký (favicon giữ nguyên emoji 👁 đã có).
2. **Sidebar điều hướng** thay topbar cũ — mục "Kỳ thi" (hoạt động) + "Cài đặt" (vô hiệu hoá, nhãn "Sắp ra mắt" — đúng tinh thần Mức B để dành, không giả vờ đã làm), role badge (Quản trị viên/Giám thị) + nút đăng xuất ở chân sidebar. Trang đăng nhập/đăng ký **không hiện sidebar** (dùng `hide_sidebar` truyền từ `pages.py`).
3. **KPI tiles trên Dashboard**: 4 ô số liệu tổng quan (đang tham gia / đang cảnh báo / điểm rủi ro trung bình / đã kết thúc), tính trực tiếp từ dữ liệu session đã có (không cần API mới), cập nhật lại mỗi khi có sự kiện WebSocket mới.
4. **Toast notification** (`showToast()` trong `api.js`) thay thế toàn bộ `alert()` và các dòng thông báo rời rạc — dùng cho: tạo kỳ thi, tạo giám thị, copy mã tham gia, lỗi tải file.
5. **Loading state**: dòng "Đang tải..." hiện ngay khi trang mở, thay bằng dữ liệu thật hoặc thông báo trống sau khi fetch xong (áp dụng cả 3 trang: kỳ thi, dashboard, chi tiết phiên).

**Kiểm tra**: 13 test trang (`test_pages.py`, có test riêng xác nhận sidebar ẩn đúng ở trang đăng nhập/đăng ký và hiện đúng ở các trang còn lại) + toàn bộ JS qua `node --check` + 1 lượt chạy `uvicorn` thật (đăng ký → tạo kỳ thi → 3 thí sinh join → xác nhận dữ liệu đúng hình dạng cho KPI). **234 test (196 CV + 38 backend) đều pass**, không regression. Vẫn còn giới hạn "chưa có trình duyệt thật để tự mắt xác nhận" như các đợt polish trước.

**Mức B vẫn để dành** — xem mục 6 bên dưới, ghi vào luận văn như hướng phát triển.

---

---

## 1. Bối cảnh & mục tiêu

Dashboard hiện tại (5 trang: login/register/exams/dashboard/session_detail) **đầy đủ chức năng, đã test kỹ** (233 test, đã chạy qua server thật) — nhưng thiết kế đang ở mức **"công cụ nội bộ chạy được"**, chưa đạt cảm giác **"sản phẩm thương mại có thương hiệu riêng"**. Cụ thể còn thiếu:

- Không có tên thương hiệu/logo — chỉ ghi chữ "Hệ thống Giám sát Thi bằng CV".
- Điều hướng chỉ có 1 dòng topbar + nút đăng xuất — không có sidebar, không phân trang theo khu vực chức năng.
- Không có màn hình tổng quan (KPI) — vào thẳng bảng chi tiết, thiếu bối cảnh "tình hình chung đang thế nào".
- Thông báo lỗi/thành công dùng `alert()` (register.js không có, nhưng vài chỗ) hoặc text rời rạc từng trang — không nhất quán.
- Thiếu hẳn 1 số trang mà 1 SaaS thật sẽ có: đổi mật khẩu, cài đặt tổ chức, quản lý danh sách giám thị riêng (hiện nhét chung vào trang Kỳ thi).
- Không có trạng thái "đang tải" (loading) — bảng trống 1 nhịp trước khi có dữ liệu, dễ hiểu nhầm là lỗi.

**Mục tiêu**: nâng cấp có chọn lọc, ưu tiên phần tạo ấn tượng mạnh nhất khi demo — không làm toàn bộ tính năng 1 SaaS thương mại đầy đủ (billing thật, multi-language, v.v. — ngoài phạm vi thời gian còn lại của đồ án, xem mục 6).

---

## 2. Nguyên tắc thiết kế xuyên suốt

- **1 hệ thống design token nhất quán** — mở rộng đúng bộ biến màu đã có trong `backend/static/style.css` (`--color-bg/surface/border/text/muted/primary/low/medium/high`), thêm scale cho font-size, spacing, bo góc, đổ bóng — thay vì các giá trị rời rạc (`8px`, `12px`, `20px`...) rải rác như hiện tại.
- **Giữ dark theme làm chính** — đã hợp lý với bản chất "phòng giám sát", nhưng thêm chiều sâu: phân lớp bề mặt rõ ràng hơn (nền < card < card nổi/hover), viền/đổ bóng tinh tế thay vì phẳng.
- **Giữ triết lý vanilla JS, không React/build step** (quyết định đã chốt từ Tuần 14, xem `docs/KE_HOACH_PLATFORM.md` mục 1) — component tái sử dụng sẽ là các hàm JS helper tạo DOM nhất quán (`createToast()`, `createButton()`...), không đổi kiến trúc.
- **Không đổi API/backend** — toàn bộ việc ở đây chỉ là template Jinja2 + CSS + JS tĩnh, không đổi endpoint/logic phía `backend/routers/`.

---

## 3. Kiến trúc thông tin (IA) — trang hiện có vs. đề xuất bổ sung

| Trang | Hiện tại | Đề xuất |
|---|---|---|
| Đăng nhập/Đăng ký | Form trơ giữa nền tối | Thêm value proposition ngắn bên cạnh form (không phải trang marketing đầy đủ — chỉ 1-2 câu + tên thương hiệu) |
| Điều hướng chính | Topbar 1 dòng (brand + đăng xuất) | **Sidebar cố định**: Kỳ thi / Giám thị / Cài đặt — đúng IA 1 SaaS quản trị thật |
| Kỳ thi | Bảng đơn giản + 2 form nhúng chìm (tạo kỳ thi, tạo giám thị) | Bảng/card kỳ thi tách riêng khỏi form quản lý giám thị (mục riêng trong sidebar) |
| Giám thị | Nhét chung trang Kỳ thi | **Trang riêng** "Quản lý giám thị" (danh sách + tạo mới) |
| Cài đặt tổ chức | Chưa có | **Trang mới**: đổi tên tổ chức (đã có API? — cần kiểm tra, có thể cần thêm `PATCH /organizations/me`) |
| Đổi mật khẩu | **Chưa có ở đâu cả** (thiếu sót thật, không chỉ thẩm mỹ) | Trang Profile cá nhân — cần thêm API mới (VD `PATCH /auth/me/password`) |
| Dashboard | Vào thẳng bảng chi tiết | Thêm **hàng KPI tổng quan** trên đầu (tổng thí sinh / đang ALERT / điểm rủi ro trung bình) trước bảng |
| Chi tiết phiên | Đã có chart + bảng vi phạm + thumbnail (đợt polish trước) | Thêm chip tổng hợp mức độ (X vi phạm MEDIUM, Y HIGH) ở đầu trang |

---

## 4. Redesign cụ thể từng phần

### 4.1. Thương hiệu
Cần 1 tên sản phẩm thật (không phải mô tả chức năng) để dùng trong logo/tiêu đề/favicon. Gợi ý vài phương án theo hướng "giám sát/toàn vẹn thi cử" (bạn chọn hoặc tự đặt tên khác — xem mục 7):
- **ProctorLens** — nhấn mạnh "ống kính giám sát"
- **ExamGuard** — trực diện, dễ hiểu
- **Giám Thị Số** — thuần Việt, dễ nhớ, phù hợp thị trường trong nước đã xác định (trường ĐH/CĐ, trung tâm khảo thí VN)
- **VeriExam** — gốc "verify" + "exam"

Logo: wordmark đơn giản (chỉ chữ, kiểu chữ có cá tính) + biểu tượng nhỏ (mắt/khiên) — không cần logo phức tạp, 1 SVG tự vẽ là đủ, tránh phụ thuộc file ảnh ngoài.

### 4.2. Layout — Sidebar thay Topbar
```
┌─────────────┬──────────────────────────────┐
│   LOGO       │  (breadcrumb / tiêu đề trang) │
│              ├──────────────────────────────┤
│ ▸ Kỳ thi     │                                │
│ ▸ Giám thị   │      nội dung trang            │
│ ▸ Cài đặt    │                                │
│              │                                │
│ ────────     │                                │
│ [role badge] │                                │
│ Đăng xuất    │                                │
└─────────────┴──────────────────────────────┘
```
Sidebar cố định bên trái (ẩn thành menu hamburger nếu màn hình hẹp — kiểm tra responsive cơ bản). Áp dụng cho mọi trang trừ login/register.

### 4.3. Dashboard — thêm KPI tiles
Trên đầu bảng hiện có, thêm 1 hàng 3-4 ô số liệu tổng quan (tổng thí sinh đang thi, số đang ALERT, điểm rủi ro trung bình, số đã kết thúc) — dữ liệu tính ngay từ danh sách session đã fetch (`GET /exams/{id}/sessions`), không cần API mới.

### 4.4. Toast notification thay `alert()`/text rời rạc
1 hàm JS dùng chung (thêm vào `api.js`): `showToast(message, type)` (type: success/error/info) — thay thế toàn bộ chỗ đang dùng `alert()` (VD `copyJoinCode` khi trình duyệt không hỗ trợ clipboard) và các `<p id="...-message">` rời rạc từng trang.

### 4.5. Loading state
Khi `loadExams()`/`loadInitialSessions()`/`loadDetail()` đang chờ fetch, hiện 1 dòng "Đang tải..." hoặc skeleton row thay vì bảng trống trơn.

---

## 5. Component nền tảng cần dựng (dùng lại nhiều nơi)

| Component | Vai trò | Cách làm (vanilla JS) |
|---|---|---|
| `Toast` | Thông báo thành công/lỗi | Hàm `showToast()`, tạo `<div>` tạm, tự biến mất sau vài giây |
| `Button` (primary/secondary/ghost/danger) | Nút bấm nhất quán | Class CSS chuẩn hoá, không cần hàm JS riêng |
| `Sidebar nav` | Điều hướng | Template Jinja2 include chung (`_sidebar.html`) |
| `KPI tile` | Số liệu tổng quan | Class CSS + hàm JS render đơn giản |
| `Empty state` | Đã có (Tuần polish trước) | Giữ nguyên, mở rộng thêm icon minh hoạ nhỏ |
| `Loading row` | Đang tải dữ liệu | Class CSS `.skeleton` (shimmer animation nhẹ) |

---

## 6. Phạm vi & đánh đổi thời gian (quan trọng nhất)

Thời gian còn lại của đồ án ưu tiên: Tuần 16 (đang chạy — bạn tự quay), Tuần 17 (đo Precision/Recall/F1 — việc quan trọng nhất còn thiếu), Tuần 18-19 (viết luận văn + demo). Làm **toàn bộ** danh sách ở mục 3-5 là không thực tế nếu không lùi tiến độ các tuần trên.

### Mức A — nên làm ngay (ước lượng 1 buổi làm việc, tạo ấn tượng thị giác mạnh nhất/thời gian bỏ ra)
1. Đặt tên thương hiệu + logo SVG đơn giản, áp dụng nhất quán (favicon, sidebar, tiêu đề trang)
2. Sidebar điều hướng thay topbar
3. KPI tiles trên Dashboard
4. Toast notification thay `alert()`/text rời rạc
5. Loading state cơ bản

### Mức B — để dành, ghi vào luận văn như hướng phát triển (không bắt buộc trước khi bảo vệ)
1. Trang Cài đặt tổ chức + trang đổi mật khẩu (**cần thêm API mới** — đây là việc backend, không chỉ giao diện)
2. Trang Quản lý giám thị tách riêng
3. Chip tổng hợp mức độ vi phạm trên trang chi tiết phiên
4. Font chữ riêng qua `@font-face` (hiện dùng font hệ thống — vẫn chuyên nghiệp, không bắt buộc đổi)
5. Kiểm tra/tối ưu responsive cho màn hình hẹp

**Khuyến nghị**: chỉ làm Mức A bây giờ. Mức B ghi rõ vào luận văn (chương Định hướng thương mại hóa / Kết luận & Hướng phát triển) — đúng tinh thần thành thật khoa học đã áp dụng xuyên suốt đồ án, không cần giả vờ đã làm hết.

---

## 7. Cần bạn quyết định trước khi bắt đầu code

1. **Tên thương hiệu**: chọn 1 trong 4 gợi ý ở mục 4.1, hay bạn tự đặt tên khác?
2. **Phạm vi**: chỉ làm Mức A ngay bây giờ (khuyến nghị), hay muốn làm cả Mức B (chấp nhận tốn thêm thời gian, có thể ảnh hưởng tiến độ Tuần 17)?
