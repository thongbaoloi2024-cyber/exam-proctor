# Kế hoạch platform (multi-tenant, cloud, dashboard giám thị)

> **Tài liệu lịch sử.** Các đoạn “đã làm/chưa làm” bên dưới mô tả từng mốc
> phát triển và có thể không còn đúng với source hiện tại. Bản hardening đã sửa
> auth cookie/XSS, WebSocket strict telemetry, snapshot upload, exam expiry,
> liveness, dependency backend nhẹ và single-worker guard. Dùng `README.md`,
> `SECURITY.md`, `backend/ws_schemas.py` và test hiện tại làm nguồn chuẩn. Kiến
> trúc quản trị ba cấp mới hơn nằm tại `docs/QUAN_TRI_VA_PHAN_QUYEN.md`.

> Viết sau khi hoàn chỉnh Tuần 1-12 (pipeline CV single-machine, xem `docs/DATA_SCHEMAS.md`, `docs/DIAGRAMS.md`, `docs/KE_HOACH_CHI_TIET_TUAN12.md`). Người dùng quyết định mở rộng đồ án thành 1 sản phẩm thương mại hóa được — không chỉ đóng gói đẹp cho 1 máy — deadline lùi 1-2 tháng để đủ thời gian. Tài liệu này ghi lại kiến trúc + lộ trình mới, đối chiếu rõ với kế hoạch Tuần 12 cũ.

---

## 1. Bối cảnh & quyết định

Kế hoạch Tuần 12 cũ (`docs/KE_HOACH_CHI_TIET_TUAN12.md`) hướng tới 1 app desktop hoàn thiện hơn: cửa sổ OpenCV, nút Start/End, tự sinh báo cáo — nhưng vẫn 1 máy, không mạng, không multi-tenant. Người dùng muốn hơn thế: nhiều học sinh thi cùng lúc, 1 giám thị xem được tất cả qua dashboard, hệ thống thuộc sở hữu của 1 tổ chức (trường/trung tâm khảo thí), không phải ai cũng dùng chung được.

**Không đổi (giữ nguyên tuyệt đối):** `src/perception/`, `src/signals/`, `src/fusion/`, `src/reporting/` — đây là phần CV tự làm, nguyên bản, là điểm khác biệt học thuật so với `exam-cheating-detection`. Lớp platform chỉ **bọc thêm bên ngoài**, không sửa logic CV.

**Đối tượng khách hàng** (B2B, tổ chức tự vận hành kỳ thi của họ):
- Trường đại học/cao đẳng, trung tâm khảo thí/chứng chỉ — không nhắm cá nhân lẻ.
- Ở mốc triển khai của tài liệu này có 2 vai trò dùng thật: **giám thị**
  (`proctor`, có tài khoản, dùng dashboard) và **thí sinh** (không có tài khoản,
  chỉ nhập tên + join-code — giữ luồng nhẹ như vào phòng Kahoot/Quizizz). Đây là
  mô hình lịch sử; hướng nâng cấp tách System Admin, Organization Admin và Exam
  Manager/Giáo viên được đặc tả riêng tại
  `docs/QUAN_TRI_VA_PHAN_QUYEN.md`.
- Định vị cạnh tranh: chi phí thấp hơn Proctorio/Honorlock/ProctorU (đã khảo sát ở Chương 3), tự host bằng Docker Compose, dữ liệu khuôn mặt lưu trong nước (thuận lợi cho tuân thủ Nghị định 13/2023, khác các SaaS nước ngoài).

**Quyết định "không video live"** (đã hỏi và chốt với người dùng): dashboard giám thị hiển thị **bảng điểm rủi ro real-time + ảnh chụp bằng chứng lúc có vi phạm**, KHÔNG phải lưới video trực tiếp kiểu Zoom/Google Meet. Lý do:
- Zoom/Meet không cấp quyền cho ứng dụng thứ 3 lấy video thô real-time của người khác để chạy AI phân tích.
- Tự xây video-conferencing thật (WebRTC SFU/MCU) là 1 mảng hạ tầng hoàn toàn khác, khối lượng lớn hơn cả phần platform này, sẽ kéo đồ án lệch khỏi trọng tâm CV.
- CV chạy **cục bộ tại máy học sinh** (không đổi — đúng lý do các sản phẩm proctoring thật cũng làm vậy: riêng tư hơn, ít băng thông hơn, không cần GPU server).

**Triển khai:** chỉ demo qua Docker Compose local lúc bảo vệ (không deploy cloud thật) — theo lựa chọn của người dùng.

**Frontend dashboard:** Jinja2 (server-rendered) + vanilla JS/WebSocket, KHÔNG dùng React. Lý do: toàn bộ kỹ năng thể hiện xuyên suốt đồ án là Python; thêm React là thêm 1 toolchain hoàn toàn mới dưới áp lực thời gian, rủi ro cho phần CV mới là trọng tâm chấm điểm. Backend thiết kế API-first (REST + WS tách khỏi phần render) nên frontend nâng cấp lên React sau này không cần đổi backend — nêu như hướng phát triển trong luận văn.

---

## 2. Kiến trúc tổng thể

```
[Máy thí sinh]                              [Docker Compose - demo "cloud" local]
main.py / client (CV engine, KHÔNG ĐỔI)      backend/ (FastAPI)
 - PerceptionLayer, 7 SignalExtractor          - REST: auth, org/exam/session CRUD
   RiskFusionEngine                             - WS /ws/client + Authorization: nhận
 - BackendClient:                                  telemetry_update/ViolationEvent/snapshot
   gửi telemetry theo lô + vi phạm                 từ client, kiểm tra rồi ghi sessions/<id>/*.jsonl
   qua WebSocket, vẫn ghi JSONL local song song       (schema cũ), update ExamSession, fan-out
                                                    cho dashboard
                                                  - WS /ws/dashboard/{exam_id}: giám thị nhận
                                                    cập nhật real-time
                                                  - PostgreSQL: Organization/User/Exam/
                                                    ExamSession (chỉ con trỏ + trạng thái,
                                                    xem docs/DATA_SCHEMAS.md mục 7)
                                                  - session_materializer.py: dựng thư mục
                                                    sessions/<id>/ đúng shape để gọi
                                                    src/reporting/generate_report() y nguyên
```

Xem `docs/DATA_SCHEMAS.md` mục 7 cho chi tiết bảng DB.

### 2.1. Lớp quản trị mục tiêu

Lớp platform sẽ phát triển từ RBAC hai role hiện tại sang **RBAC + scope**:

```text
System Admin ---- quản lý platform/tổ chức, không mặc định đọc evidence
                       |
Organization Admin ---+--- quản lý thành viên/chính sách trong một org_id
                       |
Exam Manager ----------+--- chỉ vận hành Exam có ExamAssignment hợp lệ
                       |
Candidate ---------------- token exam_session của đúng một ExamSession
```

Mọi quyết định truy cập dữ liệu kỳ thi phải kiểm tra cả capability, `org_id` và
`ExamAssignment`; ẩn menu ở frontend không thay thế kiểm tra tại REST,
WebSocket, snapshot và report download. Mô hình bảng mục tiêu, sitemap và lộ
trình migration xem `docs/QUAN_TRI_VA_PHAN_QUYEN.md`.

---

## 3. Đã làm xong (Tuần 12 mới — backend skeleton)

- `backend/models.py`, `db.py`, `auth.py` — SQLAlchemy models, JWT cho User (admin/proctor) + session token riêng cho ExamSession (thí sinh, dùng để xác thực WS).
- `backend/routers/auth.py` — đăng ký (tạo Organization + admin đầu tiên), đăng nhập, admin tạo proctor (luôn gán đúng org của admin, không nhận `org_id` từ client — điểm cách ly multi-tenant quan trọng nhất).
- `backend/routers/exams.py` — admin tạo Exam (sinh `join_code` 6 ký tự duy nhất), admin/proctor liệt kê Exam trong org của họ, thí sinh `POST /exams/join` bằng join_code + tên (không cần tài khoản) → nhận `session_token`.
- `backend/routers/sessions.py` — liệt kê phiên của 1 Exam (cho dashboard), kết thúc phiên (ghi `session_meta.json`), tải báo cáo HTML/PDF (gọi lại `src/reporting/generate_report()` nguyên bản).
- `backend/routers/ws.py` + `backend/ws_manager.py` — 2 kênh WebSocket (client gửi lên, dashboard nhận fan-out), `ConnectionManager` in-process (không Redis — quy mô 1 kỳ thi không cần message broker phân tán).
- `backend/session_materializer.py` — dựng thư mục `sessions/<id>/` đúng shape để `src/reporting/` dùng lại không đổi gì.
- `docker-compose.yml` + `Dockerfile.backend` — service `backend` (FastAPI/Uvicorn) + `db` (Postgres) + volume `sessions_data`.
- `backend/tests/` (10 test, dùng SQLite file tạm — không cần Postgres/Docker để chạy `pytest backend/tests`): `test_auth.py` (đăng ký/đăng nhập/phân quyền admin-proctor), `test_exams.py` (tạo/liệt kê/join/cách ly giữa 2 Organization), `test_sessions_ws.py` (luồng quan trọng nhất: gửi `SignalResult`/`ViolationEvent` giả qua WS → file `.jsonl` ghi đúng → DB cập nhật → `generate_report()` THẬT chạy được trên thư mục server tự dựng).

**Chưa làm trong tuần này (để lại Tuần 13+):** chưa nối `BackendClient` phía client thật (`main.py`), chưa xây dashboard UI (Jinja2 templates) — hiện chỉ có API + Swagger UI tự sinh (`/docs`), chưa động vào `AppController`/`src/ui/` (Tuần 12 cũ) hay bất kỳ file nào trong `src/`.

## 3b. Đã làm xong (Tuần 13 — Client↔Backend integration + UI/UX 1-máy)

- `config/fusion.yaml` mở rộng đúng như dự kiến Tuần 12 cũ (`camera`/`paths`/`enrollment`/`report`) + thêm mục `backend` mới (`enabled` mặc định `false` — giữ nguyên luồng 1-máy cũ khi chưa cần platform); mỗi `signals.<NAME>` có thêm tham số dựng riêng từng signal (trước đây hardcode trong `main.py`).
- `src/app_config.py` (`AppConfig.from_yaml`) + `src/signals/factory.py` (`build_signals_from_config`) — thay thế hoàn toàn `_build_other_signals()`/`IdentitySignal(...)` hardcode cũ, sửa đúng bug threshold IDENTITY đã phát hiện (main.py cũ: 0.60/0.45, YAML: 0.55/0.40 — factory giờ đọc đúng YAML).
- `src/ui/{app_state,button,text_field,overlay}.py` — state machine `AppState` (IDLE→ENROLLMENT→MONITORING→GENERATING_REPORT→ENDED) theo đúng thiết kế `docs/KE_HOACH_CHI_TIET_TUAN12.md`, IDLE mở rộng thêm `TextField` nhập Tên + Mã tham gia (chỉ hiển thị có ý nghĩa khi `backend.enabled=true`).
- `src/client/backend_client.py` — `BackendClient` dùng `websockets.sync`, gửi
  telemetry theo lô, heartbeat, vi phạm và snapshot bytes; `join_exam()` là một
  lời gọi REST ngắn. Kết nối dùng Authorization header, không đặt token trong URL.
- **Bổ sung backend** (`backend/routers/ws.py`): message `"end_session"` trên
  WebSocket `/ws/client` để chính thí sinh kết thúc phiên; endpoint REST vẫn cho
  giám thị kết thúc hộ.
- `src/app_controller.py` (`AppController`) — gộp toàn bộ luồng thành 1 `step(raw_frame)` duy nhất (thay 2 vòng lặp `while` tách biệt cũ), tích hợp `BackendClient` "best-effort" (backend chết thì phiên vẫn chạy đúng y hệt cục bộ).
- `main.py` viết lại thành entry point mỏng.
- **43 test mới** (`test_app_config`, `test_signal_factory`, `test_button`, `test_text_field`, `test_overlay`, `test_backend_client` — dùng `websockets.sync.server` thật, không mock, cho phần WebSocket — `test_app_controller`, `test_app_end_to_end_simulated` — dùng `generate_report()` thật, không fake) + 1 test backend mới (`test_client_can_end_own_session_via_websocket`). Tổng **196 test CV + 11 test backend đều pass**, không regression.
- `README.md` viết lại đầy đủ (cài đặt, chạy 1-máy, chạy với platform, cấu trúc config/session, test).

**Chưa làm (để lại Tuần 14+):** chưa có dashboard UI thật (chỉ Swagger UI/gọi API trực tiếp); chưa test qua webcam thật (máy dev vẫn không có webcam, như mọi tuần trước — người dùng cần tự chạy `python main.py` trên máy có webcam và báo lại).

### Hạn chế đã phát hiện, chưa sửa (nằm ngoài phạm vi tuần này)

1. **`backend/` không nhẹ như dự kiến ban đầu.** `src/reporting/report_generator.py` import `src.fusion.config`, và `src/fusion/__init__.py` import `.engine` → `from src.signals.base import SignalResult` — theo cơ chế import package chuẩn của Python, dòng này chạy `src/signals/__init__.py` trước, mà file đó import cả 7 signal (bao gồm `IdentitySignal`/`HeadPoseSignal`/`ObjectSignal` — kéo theo `facenet-pytorch`/`mediapipe`/`ultralytics`). Kết quả: image `backend` phải cài **toàn bộ** `requirements.txt` (dùng chung 1 file với phần CV, không tách `requirements-backend.txt` riêng như dự kiến), làm Docker image lớn hơn nhiều so với 1 backend web thuần túy. Hướng sửa khả dĩ sau này (không làm bây giờ — ngoài phạm vi đã chốt "không đụng `src/`" của tuần này): lazy-import trong `src/signals/__init__.py`.
2. **Ghim `bcrypt<4.1` trong `requirements.txt`.** `passlib` 1.7.4 (bản mới nhất hiện có) không tương thích `bcrypt>=4.1` — bước tự kiểm tra nội bộ của `passlib` (`detect_wrap_bug`) dùng 1 chuỗi test dài >72 byte, mà `bcrypt>=4.1` bắt đầu ném `ValueError` thay vì tự xử lý như bản cũ. Đã xác nhận bằng cách chạy thật: cài `bcrypt` mới nhất (5.0.0) làm mọi test liên quan đến mật khẩu crash ngay từ lần băm đầu tiên; hạ về `bcrypt==4.0.1` hết lỗi, 10/10 test pass. Nếu sau này nâng cấp `passlib`/`bcrypt`, kiểm tra lại vấn đề này trước.

---

## 3c. Đã làm xong (Tuần 14 — Dashboard giám thị)

- `backend/templates/` (Jinja2) và `backend/static/` (vanilla JS/CSS, không CDN).
  Dashboard dùng cookie HttpOnly; dữ liệu người dùng được gắn bằng DOM/textContent.
- `backend/routers/pages.py` phục vụ các trang, mount **tại tiền tố `/ui/...`** — **không phải `/exams` như dự kiến ban đầu**: phát hiện bug thật lúc code (trang HTML `/exams` trùng path với API JSON `/exams` của Tuần 12, router đăng ký trước thắng nên trang không bao giờ hiện ra, luôn trả lỗi 401 từ API) — sửa bằng cách tách hẳn namespace `/ui/...` cho mọi trang, giữ nguyên mọi path API JSON cũ.
- 2 endpoint JSON mới (`backend/routers/sessions.py`): `GET /sessions/{id}/detail` (tái dùng `load_session_report_data()` của Tuần 11 — không tự parse lại `violations.jsonl`) và `GET /sessions/{id}/snapshots/{filename}` (dùng `Path(...).name` chặn path traversal).
- Link báo cáo/snapshot dùng cookie HttpOnly cùng origin và URL đã encode; token
  không được JavaScript đọc hoặc lưu trong `localStorage`.
- **13 test backend mới** (`test_session_detail.py`, `test_pages.py`) + đã chạy **uvicorn thật** (không chỉ `TestClient`) và xác nhận toàn luồng qua HTTP/WebSocket thật (script Python dùng `websockets.sync.client` mô phỏng client/dashboard — không có trình duyệt thật trong môi trường này): đăng ký → đăng nhập → tạo exam → nhiều thí sinh join → gửi `risk_update`/`violation_event`/`end_session` → dashboard WebSocket nhận đúng fan-out real-time (đã xác nhận đúng field JSON khớp với logic đọc trong `dashboard.js`) → `GET .../detail` trả đúng violations sắp xếp theo thời gian. **220 test (196 CV + 24 backend) đều pass**, không regression.

**Giới hạn thật (chưa/không thể kiểm ở đây):** không có trình duyệt thật trong môi trường này để xác nhận trực quan JS chạy đúng (chỉ xác nhận gián tiếp qua script mô phỏng WebSocket) — cần người dùng tự mở trình duyệt thật, đăng nhập, thử luồng đầy đủ và báo lại nếu có bug UI/UX (giống đúng tinh thần "cần webcam thật" đã áp dụng xuyên suốt các tuần CV trước).

### Hoàn thiện giao diện (sau Tuần 15, trong lúc người dùng quay bộ test Tuần 16)

Rà lại toàn bộ 5 trang, hoàn thiện các phần còn dang dở:
- **Biểu đồ risk score theo thời gian** trên trang chi tiết phiên — API `GET /sessions/{id}/detail` đã trả `risk_timeline` từ Tuần 14 nhưng chưa dùng; giờ vẽ bằng SVG polyline thuần (không thêm thư viện chart, giữ đúng nguyên tắc "không CDN/không build step").
- **Ảnh chụp bằng chứng hiển thị thumbnail trực tiếp** trong bảng vi phạm (trước đây chỉ có nút "Xem ảnh" phải bấm mới thấy) — vẫn dùng cơ chế `fetch`+`Blob` cũ (không đổi, vì `<img src>` thường không tự gắn được header `Authorization`).
- **Empty state** cho bảng dashboard/danh sách kỳ thi khi chưa có dữ liệu (trước đây bảng trống không có dòng nào trông như bị lỗi).
- **Trạng thái mất kết nối/đang thử lại** hiển thị rõ trên dashboard khi WebSocket rớt (trước đây tự động thử lại ngầm, không thông báo gì cho giám thị).
- Nút **copy mã tham gia** vào clipboard trên trang danh sách kỳ thi (tiện phát cho thí sinh).
- Favicon (biểu tượng 👁) cho toàn bộ trang.

Kiểm tra: 4 test trang mới (favicon, empty-state, ws-status, risk-chart container) + toàn bộ JS được `node --check` xác nhận không lỗi cú pháp (bắt được lỗi mà test HTML-string trước đó không phát hiện được) + 1 lượt chạy `uvicorn` thật gửi `risk_update`/`violation_event` kèm ảnh snapshot thật, xác nhận `GET /sessions/{id}/detail` trả đúng hình dạng dữ liệu mà `session_detail.js` cần (field `video_time_sec`/`risk_score` cho biểu đồ, `snapshot_path` cho thumbnail). **233 test (196 CV + 37 backend) đều pass.** Vẫn còn giới hạn "chưa có trình duyệt thật để tự mắt xác nhận" như trên — về bản chất không đổi.

---

## 3d. Đã làm xong (Tuần 15 — Hoàn thiện multi-tenant + bảo mật cơ bản)

- `backend/tests/test_org_isolation.py` (5 test) — xác nhận 1 Organization không đọc/sửa được dữ liệu của Organization khác qua **mọi** endpoint có dữ liệu riêng theo tổ chức: `GET /exams/{id}/sessions`, `POST /sessions/{id}/end`, `GET /sessions/{id}/report/{fmt}`, `GET /sessions/{id}/snapshots/{filename}`, và kết nối `WS /ws/dashboard/{exam_id}` — không chỉ `GET /exams` như đã có từ Tuần 12. Có thêm test riêng xác nhận vai trò `proctor` (không chỉ `admin`) cũng bị cách ly đúng.
- `backend/tests/test_auth_token_confusion.py` (3 test) — khoá lại bằng test tự động tính chất đã thiết kế từ Tuần 12: `session_token` (thí sinh) không dùng được làm Bearer token cho API admin/proctor, và ngược lại JWT admin/proctor không dùng được làm `session_token` để giả làm 1 phiên đang thi.
- **Cả 9 test đều pass ngay từ lần chạy đầu** — xác nhận thiết kế cách ly/JWT phân loại `type` từ Tuần 12 vốn đã đúng; tuần này bổ sung bằng chứng test tự động (regression-proof) thay vì chỉ tin vào thiết kế.
- `scripts/simulate_concurrent_students.py` — script mới, giả lập N thí sinh + 1 dashboard nối tới backend **thật** (không phải `TestClient`) qua HTTP/WebSocket thật. Đã tự chạy thử với `uvicorn` thật (3 thí sinh, 30 giây): log server sạch, không lỗi; dashboard nhận đúng toàn bộ cập nhật real-time từ cả 3 phiên chạy đồng thời.
- `README.md` thêm mục "Bảo mật" (cảnh báo `JWT_SECRET_KEY` demo phải đổi khi deploy thật, tóm tắt cơ chế cách ly/token) và mục hướng dẫn dùng script mô phỏng nhiều phiên cho việc tự kiểm tra trước khi demo thật. `docker-compose.yml` thêm comment cảnh báo tại chỗ khai báo `JWT_SECRET_KEY`.
- **229 test (196 CV + 33 backend) đều pass**, không regression.

**Chưa làm (nằm ngoài phạm vi tuần này, để dành Tuần 16+):** đóng gói client thành file thực thi (PyInstaller) để phân phối cho thí sinh không cần cài Python — đã bàn với người dùng, có thể đưa vào chương "Định hướng thương mại hóa" như hướng phát triển thay vì code thật ở giai đoạn này.

---

## 4. Lộ trình các tuần tiếp theo (Tuần 13-19, thay thế Tuần 13-16 cũ)

> `docs/KE_HOACH_4_THANG_THEO_TUAN.md` cần cập nhật theo lộ trình này — xem mục cập nhật trong file đó.

- **Tuần 13 ✅ Đã xong**: Client↔Backend integration — `BackendClient` (gửi `SignalResult`/`ViolationEvent`/risk score qua WS), `AppState`/`AppController` (giữ cửa sổ OpenCV, không đổi sang PyQt) nối thêm bước đăng nhập bằng join-code + gọi backend lúc Start/End. Vẫn ghi JSONL local song song (offline-first). Xem mục 3b.
- **Tuần 14 ✅ Đã xong**: Dashboard giám thị — Jinja2 + vanilla JS/WebSocket, bảng lưới real-time, trang chi tiết 1 phiên, tải báo cáo. Xem mục 3c và `docs/BAO_CAO_TUAN14.md`.
- **Tuần 15 ✅ Đã xong**: Hoàn thiện multi-tenant + bảo mật cơ bản — test cách ly org ở mọi endpoint, test chống giả mạo chéo JWT, script mô phỏng nhiều phiên đồng thời. Xem mục 3d.
- **Tuần 16** (dời từ Tuần 13 cũ): Quay & gán nhãn bộ test — 6 kịch bản, có ít nhất 1-2 clip chạy qua toàn bộ platform (không chỉ pipeline cục bộ).
- **Tuần 17** (dời từ Tuần 14 cũ): Cài baseline + đánh giá định lượng (Precision/Recall/F1) — không đổi phương pháp, vẫn chỉ đánh giá độ chính xác CV.
- **Tuần 18** (dời từ Tuần 15 cũ): Viết chương Thiết kế/Cài đặt/Thực nghiệm, mở rộng thêm kiến trúc platform + **chương ngắn mới "Định hướng thương mại hóa"** (đối tượng khách hàng, so sánh chi phí Proctorio/Honorlock, giới hạn hiện tại/roadmap).
- **Tuần 19** (dời từ Tuần 16 cũ): Hoàn thiện luận văn + slide + demo (2 máy client kết nối 1 dashboard qua Docker Compose) + rà soát trích dẫn.

---

## 5. Liên kết tài liệu

- Data model DB: `docs/DATA_SCHEMAS.md` mục 7.
- Kiến trúc CV gốc (không đổi): `docs/DIAGRAMS.md`, `docs/DATA_SCHEMAS.md` mục 1-6.
- Kế hoạch UI/UX 1-máy cũ (tham khảo phần còn tái dùng được — `AppState`, chưa code): `docs/KE_HOACH_CHI_TIET_TUAN12.md`.
- Lộ trình tổng: `docs/KE_HOACH_4_THANG_THEO_TUAN.md`.
- Kế hoạch thiết kế lại giao diện hướng "sản phẩm thương mại" (chưa code, đang chờ quyết định tên thương hiệu + phạm vi): `docs/KE_HOACH_THIET_KE_UI.md`.
