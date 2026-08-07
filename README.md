# Hệ thống giám sát thi bằng Computer Vision

Ứng dụng gồm ba phần:

- Browser extension Chrome/Firefox chạy nền trong phiên thi, quản lý luồng
  tham gia, thiết bị và tính toàn vẹn trình duyệt.
- Client desktop Python chạy webcam và pipeline CV bảy tín hiệu; đây là module
  CV riêng/legacy, chưa được port hoàn toàn sang WebAssembly/WebGPU.
- Backend FastAPI + dashboard giám thị, hỗ trợ nhiều tổ chức, kỳ thi và phiên thi.

Luồng chính:

`Webcam → Perception → 7 tín hiệu → State Machine → Risk Fusion → Violation → JSONL/ảnh → Báo cáo/dashboard`

Luồng extension:

`Mã thi → chính sách xác thực → manual/Google → kiểm tra quyền → WebSocket ticket → monitor nền → browser_events.jsonl → dashboard/báo cáo`

Bảy tín hiệu hiện có là `FACE_PRESENCE`, `MULTI_FACE`, `EYE_STATE`,
`MOUTH_STATE`, `OBJECT_PRESENCE`, `HEAD_POSE` và `IDENTITY`. Client không
stream video liên tục lên backend; chỉ gửi telemetry đã gom theo chu kỳ và ảnh
bằng chứng tại thời điểm sinh vi phạm.

## Quản trị và phân quyền

Backend đã triển khai ba mức quản trị bằng capability + tenant/resource scope:

| Vai trò | Phạm vi chính |
|---|---|
| `system_admin` | Quản lý platform, tổ chức, hạn mức, vận hành và audit toàn cục; không mặc định xem bằng chứng thí sinh |
| `org_admin` | Quản lý thành viên, vai trò, chính sách và audit của một tổ chức; không vận hành kỳ thi |
| `exam_manager` | Chỉ tạo/vận hành kỳ thi do mình sở hữu hoặc được phân công |

`User.role` (`admin/proctor`) vẫn được dual-write để tương thích với client cũ;
quyết định quyền mới đọc `OrganizationMembership`, `SystemRole` và
`ExamAssignment`. Exam Manager chỉ thấy kỳ thi được giao. System Admin bắt buộc
MFA và chỉ đọc evidence khi có break-glass grant được Organization Admin duyệt.
Chi tiết tại [docs/QUAN_TRI_VA_PHAN_QUYEN.md](docs/QUAN_TRI_VA_PHAN_QUYEN.md).

## Các thay đổi an toàn quan trọng

Phiên bản này đã được harden so với bản demo ban đầu:

- Dashboard chỉ dựng DOM bằng `textContent`/API an toàn, không chèn dữ liệu thí
  sinh vào `innerHTML`; CSP và các security header được bật.
- JWT dashboard nằm trong cookie `HttpOnly`, `SameSite=Strict`; WebSocket không
  còn đặt token trong URL/query string.
- Mọi message WebSocket được kiểm tra bằng schema chặt. Server tự gắn thời gian,
  kiểm tra đầy đủ bảy signal, tính lại risk score và đối chiếu state/severity/
  contribution trước khi nhận một vi phạm.
- Ảnh bằng chứng được upload thật dưới dạng JPEG/PNG, giới hạn 2 MiB, kiểm tra
  magic bytes/hash và lưu bằng tên do server sinh. Báo cáo chỉ được đọc ảnh nằm
  trong đúng thư mục `snapshots` của phiên.
- Telemetry mặc định gửi mỗi 1 giây thay vì mỗi frame. Server có giới hạn kích
  thước/tần suất message, heartbeat, idle timeout và trạng thái
  `pending/active/disconnected/ended`.
- Kỳ thi có lifecycle `draft/scheduled/open/closed/archived`, optimistic locking,
  join code có thời hạn và có thể xoay mã. Rate limit dùng Redis khi cấu hình,
  nếu không dùng bộ đếm in-process cho development một worker.
- Thay đổi role/assignment làm token cũ mất hiệu lực; WebSocket dashboard kiểm
  tra lại quyền định kỳ. Audit log ghi thay đổi quyền và truy cập evidence.
- Production không chấp nhận JWT secret/DB password mặc định. Docker backend chỉ
  cài dependency web/reporting nhẹ.
- Enrollment có thử thách chớp mắt `mở → nhắm → mở` trước khi chấp nhận
  embedding. Đây là liveness cơ bản, không phải bộ chống deepfake chuyên dụng.
- `report.formats` được tôn trọng; nhãn mắt nhắm là `EYES_CLOSED`; resource được
  đóng cả khi enrollment hoặc vòng camera thất bại.
- Mỗi kỳ thi chọn một trong hai chế độ thí sinh: `manual` (họ tên + mã thí
  sinh) hoặc `google`. Google dùng Authorization Code + PKCE/state/nonce;
  backend không lưu Google access token/refresh token và chỉ cấp opaque token
  thiết bị có TTL/thu hồi cho lần sau.
- Browser WebSocket dùng ticket ngẫu nhiên một lần, 30 giây, qua
  `Sec-WebSocket-Protocol`; session JWT thật vẫn chỉ đi trong REST
  `Authorization` header.
- Risk CV và browser-integrity score được lưu/hiển thị riêng. Server tự chấm
  mức độ cho chuyển tab, fullscreen, clipboard, điều hướng và tình trạng thiết
  bị; client không được tự khai severity.

Chi tiết threat model và giới hạn còn lại nằm trong [SECURITY.md](SECURITY.md).

## Yêu cầu

- Python 3.11 hoặc 3.12.
- Webcam cho chạy thật; test tự động không cần webcam.
- Docker + Docker Compose nếu chạy backend với PostgreSQL.
- Node.js 20+ để test/build browser extension.
- Kết nối mạng ở lần đầu để tải model. Weight không nằm trong source ZIP.

## Cài client CV

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Muốn chạy offline trong ngày thi/demo, hãy tải và khởi tạo toàn bộ model trước:

```bash
python scripts/prefetch_models.py
```

Model được cache trong `models/` và bị loại khỏi Git/source ZIP. Sau khi cài
dependency và prefetch thành công, client không cần mạng khi
`backend.enabled: false`.

## Build và cài browser extension

```bash
cd extension
npm test
npm run build
```

Nạp `extension/dist/chrome` bằng **Load unpacked** tại
`chrome://extensions`, hoặc chọn `extension/dist/firefox/manifest.json` tại
`about:debugging#/runtime/this-firefox`. Hướng dẫn Google OAuth, ký/publish và
threat model riêng nằm trong [extension/README.md](extension/README.md).

Extension dùng một cửa sổ monitor có preview để giữ camera/microphone/
screen-share. Background service theo dõi sự kiện và giữ WebSocket bằng
heartbeat; hệ thống không quay camera ẩn và không stream video liên tục.

## Chạy một máy, không có backend

Trong `config/fusion.yaml`, giữ:

```yaml
backend:
  enabled: false
```

Sau đó chạy:

```bash
python main.py
```

Luồng giao diện: bấm **Bắt đầu** → hoàn thành thử thách chớp mắt và đăng ký
khuôn mặt → giám sát → bấm **Kết thúc** hoặc `q`/ESC → sinh báo cáo theo
`report.formats`.

## Chạy backend cục bộ

Backend development mặc định dùng file SQLite `datt.db`; không dùng credential
PostgreSQL giả định.

```bash
python -m pip install -r requirements-backend.txt
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Đặt chuỗi vừa sinh vào `JWT_SECRET_KEY`, rồi chạy một worker:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Trong development, `/docs` được bật. Dashboard ở `/ui/login`; đăng ký tổ chức
lần đầu tại `/ui/register`.

## Chạy backend bằng Docker Compose

```bash
cp .env.example .env
```

Thay `JWT_SECRET_KEY`, `POSTGRES_PASSWORD` và `MFA_ENCRYPTION_KEY` trong `.env`.
Sinh Fernet key cho MFA bằng:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Sau đó chạy:

```bash
docker compose up --build
```

Compose chạy ở `APP_ENV=production`, vì vậy sẽ dừng ngay nếu thiếu secret hoặc
mật khẩu DB. Với local HTTP, giữ `COOKIE_SECURE=false`; khi đặt sau HTTPS reverse
proxy phải dùng `COOKIE_SECURE=true`, `FORCE_HTTPS=true` và cấu hình
`ALLOWED_HOSTS` đúng hostname.

Compose chạy PostgreSQL, Redis, backend và `report-worker`. Redis cung cấp
distributed rate limit, WebSocket dashboard pub/sub và lease chống hai worker
nhận đồng thời cùng một candidate session. Compose mặc định vẫn chạy một worker;
khi tăng `WEB_CONCURRENCY`, `REDIS_URL` là bắt buộc và volume evidence phải được
chia sẻ giữa các worker.

Tạo System Admin bằng bootstrap CLI, không có public registration:

```powershell
$env:SYSTEM_ADMIN_BOOTSTRAP_PASSWORD="mat-khau-manh-toi-thieu-12-byte"
python scripts/bootstrap_system_admin.py --email system-admin@example.edu
```

Đăng nhập tại `/ui/login`, sau đó hoàn tất MFA tại `/ui/mfa`. Khu vực
System Admin được tách rõ thành tổng quan (`/ui/system`), danh sách/chi tiết
tổ chức (`/ui/system/organizations`), bảo mật và break-glass
(`/ui/system/security`), dữ liệu được cấp quyền tạm thời
(`/ui/system/evidence`) và nhật ký toàn hệ thống (`/ui/system/audit`).
Tenant nội bộ `slug=system` không xuất hiện trong danh mục khách hàng và
không thể bị khóa qua API. System Admin chỉ thấy exam/session khi chính tài
khoản đó có break-glass grant đang active; mã tham gia và URL bài thi luôn bị
ẩn trong phạm vi này.
Các giao diện theo tenant tiếp tục tại `/ui/organization`, `/ui/exams` và
`/ui/exams/{exam_id}/manage`.

Chế độ Google là tùy chọn. Khi bật, cấu hình bốn biến bắt buộc sau và đăng ký
callback HTTPS tương ứng trong Google Cloud Console:

```dotenv
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_CALLBACK_URL=https://proctor.example.edu/candidate-auth/google/callback
OAUTH_EXTENSION_REDIRECT_URIS=https://<extension-id>.chromiumapp.org/google
```

Trang setup của extension hiển thị chính xác redirect URI của chính bản cài
đó. Để trống toàn bộ các biến trên nếu chỉ dùng chế độ manual.

## Nối client với platform

1. Exam Manager tạo kỳ thi, cấu hình ở trạng thái `draft`, phân công nhân sự
   rồi chuyển sang `open` để phát join code. Organization Admin chỉ quản trị
   tenant và cấp membership `exam_manager`, không có quyền truy cập kỳ thi.
2. Thí sinh cài extension, nhập backend + join code. Extension chỉ hiện đúng
   chế độ xác thực của kỳ thi.
3. Thí sinh đồng ý chính sách, kiểm tra camera/microphone và kích hoạt cửa sổ
   monitor. Tab bài thi chỉ được đưa lên sau bước này.
4. Giám thị mở `/ui/exams/{exam_id}/dashboard` để xem riêng risk CV, integrity
   browser, trạng thái thiết bị, timeline và báo cáo.
5. Đóng kỳ thi hoặc xoay join code khi không còn nhận thêm thí sinh.

Muốn chạy desktop CV legacy, đặt `backend.enabled: true` trong
`config/fusion.yaml` và tạo kỳ thi không bắt buộc extension. Việc hợp nhất
native CV và extension vào cùng một session cần native-messaging bridge, chưa
nằm trong bản này.

Nếu backend mất kết nối, client vẫn ghi log và báo cáo cục bộ. Dashboard sẽ đánh
dấu phiên `disconnected`; dữ liệu sinh trong thời gian offline không tự đồng bộ
lại sau đó.

## Dữ liệu phiên

```text
sessions/<session_id>/
├── session_meta.json
├── signals.jsonl
├── state_transitions.jsonl
├── browser_events.jsonl
├── violations.jsonl
├── risk_score_timeline.jsonl
├── snapshots/
├── report.html              # nếu yêu cầu HTML
└── report.pdf               # nếu yêu cầu PDF
```

Backend chỉ append vào danh sách file đã cho phép và chỉ phục vụ file thuộc đúng
tổ chức/phiên. `client_timestamp` chỉ dùng cho audit; thời gian chuẩn trong log
server do backend sinh.

## Test

Cài `requirements.txt`, sau đó:

```bash
pytest -q backend/tests tests
```

Suite gồm unit test, API/auth/org isolation, Google OIDC flow giả lập,
WebSocket ticket/event validation, upload snapshot, report, simulated video và
smoke test với MTCNN, FaceNet, MediaPipe FaceLandmarker, YOLOv8n thật. Xem kết
quả kiểm thử chốt trong file bàn giao/CHANGELOG.

Kiểm tra bổ sung:

```bash
python -m compileall -q backend src scripts main.py
node --check backend/static/api.js
```

## Tác vụ nền và retention

API có thể tạo report job bằng
`POST /sessions/{session_id}/report-jobs/{html|pdf}`. Docker Compose chạy worker
tự xử lý hàng đợi; khi chạy thủ công dùng:

```bash
python scripts/report_worker.py
```

Kiểm tra dữ liệu đã quá hạn mà chưa xóa:

```bash
python scripts/cleanup_retention.py
```

Chỉ khi đã kiểm tra danh sách dry-run mới chạy
`python scripts/cleanup_retention.py --apply`. Tác vụ xóa thư mục evidence,
review/report job liên quan và ẩn danh row phiên, đồng thời ghi audit.

`tests/manual_webcam_demo.py` dành cho kiểm tra thủ công camera/ánh sáng/góc mặt
trên máy triển khai.

## Giới hạn cần hiểu đúng

Server có thể bác telemetry không nhất quán, phát hiện mất heartbeat và không còn
tin đường dẫn file/timestamp/risk do client gửi. Tuy nhiên, phần mềm chạy trên máy
do thí sinh kiểm soát vẫn có thể bị sửa để tạo cả một chuỗi telemetry giả nhưng
nhất quán. Không thể giải quyết tuyệt đối điều đó chỉ bằng Python phía client.

Extension cũng không thể tự nhìn thấy ứng dụng ngoài trình duyệt, điện thoại thứ
hai hay máy ảo. Google login xác minh quyền sở hữu tài khoản, không xác minh
người đang ngồi trước camera.

Để dùng trong kỳ thi có rủi ro cao cần thêm ít nhất: extension được ký và
force-install bằng managed browser, client/native companion được ký và quản lý,
secure boot/attestation hoặc lockdown browser, liveness/anti-replay chuyên dụng,
HTTPS bắt buộc, audit vận hành, object storage/backup phù hợp và chính sách bảo
vệ dữ liệu. Hệ thống hiện phù hợp nghiên cứu, đồ án và triển khai có kiểm soát;
không coi đây là lockdown browser/remote-attestation hoàn chỉnh.

Các tài liệu `docs/BAO_CAO_TUAN*.md` và `docs/KE_HOACH_*.md` ghi lại lịch sử phát
triển; nếu có khác biệt, README, SECURITY và code/test hiện tại là nguồn chuẩn.
Kiến trúc quản trị ba cấp trong `docs/QUAN_TRI_VA_PHAN_QUYEN.md` là nguồn chuẩn
cho phần nâng cấp RBAC sắp tới, đồng thời luôn ghi rõ phần nào chưa triển khai.
