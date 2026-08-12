# Chương 5. Cài đặt hệ thống

## 5.1. Tổng quan

Chương 4 đã trình bày các giải pháp ở cấp kiến trúc. Chương này mô tả cách các giải pháp đó được hiện thực trong repository. Nội dung chỉ sử dụng cấu trúc file, interface và thông số đang tồn tại; các đoạn mã giả của phiên bản thiết kế ban đầu không còn được xem là implementation.

Hệ thống gồm ba phần có vòng đời độc lập:

1. Desktop client Python chạy pipeline CV và có thể hoạt động cục bộ.
2. Browser extension giám sát tính toàn vẹn trình duyệt.
3. Backend FastAPI, dashboard và worker quản lý tập trung.

## 5.2. Công nghệ sử dụng

### 5.2.1. Desktop CV

| Công nghệ | Vai trò |
|---|---|
| Python 3.11 | Ngôn ngữ chính của desktop client và backend |
| OpenCV | Đọc webcam, resize/chuyển màu, PnP, hiển thị UI và lưu ảnh |
| NumPy | Biểu diễn frame, vector và phép tính hình học |
| MediaPipe 0.10.14 | Face Landmarker theo Tasks API |
| `facenet-pytorch` | MTCNN crop/align và InceptionResnetV1 embedding |
| Ultralytics YOLOv8 | Phát hiện `cell phone` và `book` bằng model COCO |
| PyYAML/Pydantic | Đọc và kiểm tra cấu hình/hợp đồng dữ liệu |
| Jinja2, Matplotlib, xhtml2pdf | Sinh báo cáo HTML, biểu đồ và PDF |

Các phiên bản được giới hạn trong `requirements.txt` nhằm tránh xung đột giữa OpenCV, MediaPipe và NumPy. Model Face Landmarker và YOLO được đặt trong thư mục `models/`; model có thể được tải khi khởi tạo nếu chưa có.

### 5.2.2. Nền tảng web

| Công nghệ | Vai trò |
|---|---|
| FastAPI/Uvicorn | REST API, trang web và WebSocket endpoint |
| SQLAlchemy | ORM cho dữ liệu nền tảng |
| SQLite/PostgreSQL | SQLite cho phát triển; PostgreSQL cho Docker Compose |
| Redis | Rate limit phân tán, lease client và pub/sub dashboard khi được cấu hình |
| Jinja2 + JavaScript thuần | Dashboard và giao diện quản trị server-rendered |
| JWT, bcrypt, TOTP | Phiên đăng nhập, băm mật khẩu và MFA |
| Google Auth/OIDC | Xác thực Google cho nhân sự/thí sinh theo luồng tương ứng |

Backend container dùng `requirements-backend.txt`, không cài các model CV nặng. Các module dùng chung được lazy import để report vẫn hoạt động mà không khởi tạo PyTorch, MediaPipe hoặc Ultralytics.

### 5.2.3. Browser Extension

Extension dùng JavaScript theo WebExtensions API và Manifest V3. Script build tạo hai gói `dist/chrome` và `dist/firefox`; Chrome dùng service worker, còn Firefox dùng background scripts và khai báo riêng cho Gecko. Extension không sử dụng framework frontend, giúp giảm bundle và giới hạn dependency phía client không tin cậy.

## 5.3. Cấu trúc repository

Cấu trúc rút gọn của mã nguồn thực tế như sau:

```text
exam-proctor-extension-upgrade/
├── main.py
├── config/
│   └── fusion.yaml
├── src/
│   ├── app_config.py
│   ├── app_controller.py
│   ├── orchestrator.py
│   ├── client/
│   │   └── backend_client.py
│   ├── perception/
│   │   ├── pipeline.py
│   │   ├── perception_result.py
│   │   ├── face_detector.py
│   │   ├── face_mesh_detector.py
│   │   ├── object_detector.py
│   │   ├── face_embedder.py
│   │   └── head_pose_math.py
│   ├── signals/
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── face_presence.py, multi_face.py
│   │   ├── eye_state.py, mouth_state.py
│   │   ├── object_signal.py, head_pose.py
│   │   ├── identity.py, liveness.py
│   ├── fusion/
│   │   ├── signal_state_machine.py
│   │   ├── tracker.py, session.py, engine.py
│   │   ├── violation_event.py
│   │   └── *_logger.py
│   ├── reporting/
│   │   ├── data_loader.py, aggregator.py
│   │   ├── charts.py, report_generator.py
│   │   └── templates/report_template.html
│   └── ui/
├── extension/
│   ├── manifest.base.json
│   ├── src/
│   │   ├── setup.html, setup.js
│   │   ├── background.js
│   │   ├── content-monitor.js
│   │   └── common.js, styles.css
│   └── scripts/build.mjs
├── backend/
│   ├── main.py, models.py, db.py
│   ├── auth.py, authorization.py, policies.py
│   ├── ws_schemas.py, ws_manager.py, ws_tickets.py
│   ├── session_materializer.py
│   ├── routers/
│   ├── templates/
│   └── static/
├── scripts/
├── tests/ và backend/tests/
├── Dockerfile.backend
└── docker-compose.yml
```

Các package được chia theo trách nhiệm thay vì theo từng màn hình. `main.py` chỉ dựng dependency và chạy camera loop; logic phiên nằm trong `AppController`. Backend router không tự cài lại quy tắc quyền mà gọi `authorization.py`.

## 5.4. Cấu hình tập trung

`config/fusion.yaml` là nguồn cấu hình trung tâm cho desktop client. File gồm:

- Độ dài cửa sổ và bốn ngưỡng state machine của từng signal.
- Trọng số bảy tín hiệu và ngưỡng `T_enter/T_exit` cấp phiên.
- Tham số đặc thù như EAR, góc yaw/pitch, chu kỳ identity và thời lượng debounce.
- Camera, thư mục phiên, enrollment/liveness, định dạng báo cáo và kết nối backend.

`AppConfig.from_yaml()` đọc phần cấu hình cấp ứng dụng. `build_signals_from_config()` dựng đúng bảy Signal Extractor. `RiskFusionEngine.from_config()` dựng state tracker, trọng số và hysteresis từ cùng file. Cách này loại bỏ lỗi phiên bản cũ khi ngưỡng Identity được hard-code khác YAML.

Các giá trị chính đang sử dụng được trình bày ở Chương 4, Bảng 4.1. Mọi tham số được kiểm tra miền hợp lệ; ví dụ thời gian telemetry phải dương, định dạng report chỉ nhận `html/pdf`, và `T_exit` phải nhỏ hơn `T_enter`.

Policy nền tảng web không dùng trực tiếp `fusion.yaml`. `backend/policies.py` định nghĩa `PlatformPolicy`, `OrganizationPolicy` và `ResolvedExamPolicy`; backend resolve sàn hệ thống, policy tổ chức và override kỳ thi tại thời điểm tạo/cập nhật.

## 5.5. Cài đặt desktop CV client

### 5.5.1. Vòng đời ứng dụng

`main.py` thực hiện bốn việc: đọc cấu hình, dựng bảy signal, dựng `PerceptionLayer`, tạo `AppController` và chạy vòng lặp webcam. Vòng đời phiên được biểu diễn bởi `AppState`:

```text
IDLE → ENROLLMENT → MONITORING → GENERATING_REPORT → ENDED
```

`AppController.step(frame)` là điểm xử lý duy nhất cho mỗi frame. Chuột và bàn phím được đưa qua `handle_mouse()` và `handle_key()`. Cấu trúc này thay cho nhiều vòng `while` tách biệt, giúp việc kết thúc phiên, đóng log và kiểm thử chuyển trạng thái nhất quán hơn.

Khi `backend.enabled=false`, người dùng có thể chạy hoàn toàn cục bộ. Khi bật backend, màn hình IDLE yêu cầu tên và mã tham gia, gọi REST để nhận session token rồi khởi tạo `BackendClient`. Mất backend không làm pipeline cục bộ dừng; việc gửi mạng là best-effort.

### 5.5.2. Perception Layer

`PerceptionLayer.process(raw_frame_bgr)` thực hiện:

1. Resize giữ tỉ lệ và chuyển BGR sang RGB.
2. Chạy MTCNN để lấy danh sách `FaceBox`.
3. Chạy MediaPipe Face Landmarker cho khuôn mặt chính.
4. Chạy YOLO theo chu kỳ `object_detect_interval_sec`, mặc định 0,4 giây.
5. Đóng gói kết quả vào `PerceptionResult`.

YOLO không trả rỗng ở frame bị throttle mà dùng `_last_objects`. Mỗi detector được gọi qua `_safe_call()`: MTCNN/Face Landmarker lỗi thì dùng kết quả thiếu an toàn; YOLO lỗi thì giữ kết quả gần nhất. Thời gian từng bước được lưu trong `last_timings` cho benchmark.

`PerceptionResult` chứa timestamp, kích thước frame, face boxes, face landmarks, object boxes và RGB frame. Signal không gọi lại detector, nhờ vậy kết quả của một frame có cùng mốc thời gian.

### 5.5.3. Hợp đồng Signal Extractor

`src/signals/base.py` định nghĩa abstract `SignalExtractor` và dataclass `SignalResult`. Mỗi kết quả gồm:

```text
signal_name, timestamp, value,
exceeds_threshold, confidence, metadata
```

Các cài đặt cụ thể:

- `FacePresenceSignal` dùng timer vắng mặt.
- `MultiFaceSignal` lọc face box theo confidence trước khi đếm.
- `EyeStateSignal` tính EAR từng mắt bằng tọa độ pixel và yêu cầu cả hai mắt cùng nhắm.
- `MouthStateSignal` tính tỉ lệ mở miệng và activity ratio trong cửa sổ.
- `ObjectSignal` đọc box đã lọc `cell phone/book` và debounce thời lượng.
- `HeadPoseSignal` gọi `solve_head_pose()` rồi theo dõi yaw/pitch vượt ngưỡng.
- `IdentitySignal` enrollment nhiều embedding, re-verify định kỳ, có vùng warning và yêu cầu lỗi liên tiếp.

Khi thiếu landmark, signal phụ thuộc landmark trả confidence 0 và không tự kết luận bất thường; Face Presence xử lý nguyên nhân vắng mặt. Cách phân trách nhiệm tránh việc cùng một lỗi detector làm nhiều tín hiệu đồng loạt báo vi phạm.

### 5.5.4. Enrollment và liveness

Trong trạng thái ENROLLMENT, `BlinkLivenessChallenge` theo dõi chuỗi mở–nhắm–mở mắt. Chỉ sau khi challenge đạt yêu cầu, controller mới thu frame để tạo embedding tham chiếu. Số frame, số lần thử và timeout lấy từ cấu hình.

`IdentitySignal.enroll()` bỏ các frame không trích được mặt và lấy trung bình embedding hợp lệ. Nếu không có frame hợp lệ sau số lần thử, phiên được hủy với lý do enrollment failed. Liveness này là biện pháp cơ bản, không được cài đặt như anti-replay chuyên dụng.

### 5.5.5. Orchestrator và Risk Fusion

`PipelineOrchestrator` gọi Perception Layer, lần lượt chạy toàn bộ signal và cập nhật state machine. Orchestrator còn ghi `signals.jsonl`, thống kê thời gian xử lý và reset mọi signal khi bắt đầu phiên mới.

`SignalStateTracker` chứa một `SignalStateMachine` riêng cho từng tín hiệu. `RiskFusionEngine.update()` lưu kết quả mới nhất, cập nhật tracker, tính:

$$
R=\sum_i w_i\,stateValue_i
$$

sau đó gọi `SessionHysteresis`. Nếu transition đi vào `SESSION_ALERT`, engine tạo `ViolationEvent`, chọn primary violation, lưu contributing signals và snapshot. Trong khi phiên vẫn ALERT, lời gọi tiếp theo không tạo event trùng.

`StateTransitionLogger` và `RiskScoreLogger` ghi riêng transition và timeline. Việc tách logger cho phép module report đọc lại trạng thái mà không phải chạy lại model.

### 5.5.6. Gửi dữ liệu đến backend

`BackendClient` mở WebSocket nền và có hàng đợi gửi. Telemetry được gom theo `telemetry_interval_sec` thay vì gửi mọi frame. Violation event được serialize cùng contributing signals; nếu có snapshot, client đọc bytes và gửi nội dung/hash thay vì gửi đường dẫn filesystem cục bộ.

Khi kết nối không thành công, hàm gửi trở thành no-op có kiểm soát và phiên vẫn ghi file local. Điểm giới hạn là dữ liệu phát sinh trong thời gian offline chưa có cơ chế đồng bộ bù đầy đủ khi kết nối trở lại.

## 5.6. Cài đặt browser extension

### 5.6.1. Manifest và quyền

`manifest.base.json` khai báo các quyền `alarms`, `identity`, `scripting`, `storage`, `tabs` và host permission dạng optional. Extension chỉ yêu cầu origin của backend/trang thi khi cần. Content Security Policy của extension giới hạn script/style từ chính extension và chỉ cho phép kết nối HTTPS/WSS hoặc localhost phục vụ phát triển.

### 5.6.2. Luồng setup

`setup.html/setup.js` cung cấp giao diện:

1. Nhập backend và mã tham gia.
2. Lấy policy kỳ thi.
3. Chọn luồng manual hoặc Google.
4. Yêu cầu host permission đúng origin.
5. Hiển thị consent và kiểm tra điều kiện.
6. Gửi lệnh bắt đầu đến background.

Google login sử dụng `identity.launchWebAuthFlow()`. Backend quản lý state, PKCE, nonce và grant một lần; extension lưu opaque candidate device token do hệ thống cấp, không lưu token Google.

### 5.6.3. Background worker

`background.js` giữ trạng thái phiên trong `storage.session`, quản lý device ID, mở tab bài thi, inject content monitor và kết nối WebSocket. Nó theo dõi:

- Tab được active, tab mới, navigation và đóng tab.
- Focus cửa sổ.
- Health alarm và reconnect.
- Sequence của browser event và hàng đợi chưa gửi.

WebSocket được mở bằng ticket của phiên thay vì đặt bearer token trong query string. Heartbeat và event queue giúp backend biết trạng thái kết nối. Các event quan trọng được ưu tiên giữ trong hàng đợi; khi socket sẵn sàng, background flush theo thứ tự.

### 5.6.4. Content monitor

`content-monitor.js` chạy trong origin bài thi. Module yêu cầu camera/microphone và `getDisplayMedia()` theo policy, hiển thị preview/trạng thái, theo dõi track bị muted/ended và tạo banner yêu cầu quay lại toàn màn hình. Nó ghi các sự kiện clipboard, context menu, visibility/focus và permission missing.

Extension chủ yếu quan sát và cảnh báo trong phạm vi API trình duyệt. Nó không thể bảo đảm chặn ứng dụng native, máy ảo hoặc thiết bị thứ hai.

## 5.7. Cài đặt backend và dashboard

### 5.7.1. Khởi tạo FastAPI

`backend/main.py` tạo FastAPI app, mount static files và đăng ký các router:

- `auth`: đăng ký, đăng nhập, MFA, invitation và tài khoản.
- `candidate_auth`: manual/Google authentication cho thí sinh.
- `exams`: tạo, cập nhật, lifecycle, assignment, readiness và join.
- `organizations`: hồ sơ, thành viên, policy, grant và audit.
- `sessions`: danh sách/chi tiết phiên, kết thúc/reset, incident review, evidence và report job.
- `system`: dashboard hệ thống, tổ chức, policy, security và access grant.
- `ws`: kênh client và dashboard.
- `pages`: các trang Jinja2.

Middleware sinh `X-Request-ID`, áp dụng security header, điều khiển HTTPS và `Cache-Control`. CORS cho extension chỉ bật với danh sách origin cấu hình.

### 5.7.2. Mô hình dữ liệu

`backend/models.py` dùng SQLAlchemy 2.0 typed mapping. Các entity được chia thành:

- **Identity/quyền:** `User`, `SystemRole`, `OrganizationMembership`, `ExamAssignment`, `Invitation`, các bảng challenge/OAuth.
- **Tổ chức/chính sách:** `Organization`, `PlatformPolicySetting`, `AccessGrant`, `AuditLog`.
- **Kỳ thi/phiên:** `Exam`, `ExamSession`, `CandidateIdentity`, `CandidateDevice`.
- **Sau giám sát:** `IncidentReview`, `ReportJob`.

Unique constraint ngăn một candidate number hoặc candidate identity tạo nhiều phiên trong cùng kỳ thi. `ExamSession` lưu risk/integrity và trạng thái thiết bị mới nhất để dashboard không phải quét JSONL.

### 5.7.3. Xác thực và phân quyền

`backend/auth.py` phân biệt user token với session token bằng claim/type riêng. Dashboard web dùng cookie `HttpOnly`, `SameSite=Strict`. Password được băm bằng bcrypt; System Admin phải có MFA.

`authorization.py` định nghĩa enum `Permission` và mapping:

- Role tổ chức → capability tổ chức.
- Assignment `owner/manager/proctor` → capability kỳ thi.
- System role → capability nền tảng.

`authorize_exam()` và `authorize_session()` thực hiện tenant/resource scope. System Admin không được rơi xuống quyền Organization Admin; quyền evidence chỉ được thêm khi có active break-glass grant đúng tổ chức. `capabilities_for_user()` phục vụ navigation tổng quát, còn action trên từng kỳ thi dùng `exam_access_for_user()` để tránh hợp nhất nhầm quyền.

Thay đổi membership/role làm tăng `session_version` hoặc khiến record không active, do đó token cũ bị từ chối ở lần kiểm tra tiếp theo. Dashboard WebSocket định kỳ kiểm tra lại quyền thay vì chỉ xác thực lúc mở kết nối.

### 5.7.4. Policy resolution

`backend/policies.py` kiểm tra semantic version và resolve policy theo ba cấp. Boolean bắt buộc dùng phép OR với sàn cấp trên; minimum version chọn phiên bản nghiêm ngặt hơn; thời gian mất focus chọn mức nhỏ hơn. Backend từ chối override làm yếu policy, không phụ thuộc vào validation frontend.

### 5.7.5. WebSocket và validation

`ws_schemas.py` sử dụng Pydantic với `extra="forbid"`. `TelemetryUpdateData` yêu cầu đúng bảy signal và bảy state không trùng. Số phải hữu hạn và nằm trong miền. `ViolationEventData` yêu cầu contributing signals không rỗng, timestamp có timezone và không chấp nhận `snapshot_path` do client điều khiển.

`routers/ws.py` xử lý client hello, heartbeat, telemetry, violation, browser event và end session. Backend dùng thời gian nhận server, kiểm tra sequence/deduplication và tính hoặc đối chiếu lại:

- Risk score từ signal state và trọng số.
- Session state và severity.
- Primary/contributing signal.
- Browser event severity, integrity score và trạng thái thiết bị.

`ConnectionManager` giữ socket client/dashboard. Khi `REDIS_URL` được cấu hình, Redis lease ngăn hai client cùng chiếm một session và Redis pub/sub chuyển cập nhật dashboard giữa các process. Khi không có Redis, manager hoạt động in-process cho môi trường phát triển một worker.

Dashboard browser lấy ticket dùng một lần từ REST trước khi mở WebSocket. `WebSocketTicketStore` đặt thời hạn ngắn và consume ticket khi sử dụng, giảm rủi ro replay.

### 5.7.6. Giao diện web

Giao diện dùng template Jinja2 cho shell và JavaScript gọi API. Các trang chính gồm:

- System overview, organization detail, policy, security và audit.
- Organization overview, members và settings.
- Exam workspace, danh sách kỳ thi, manage/readiness/dashboard.
- Session detail, risk chart, evidence, review và report.
- Account, login, MFA và registration.

Dữ liệu server được đưa vào DOM bằng `textContent` hoặc helper an toàn. Capability quyết định menu và action hiển thị, nhưng backend vẫn là điểm enforcement cuối cùng.

## 5.8. Giao diện và luồng vận hành của hệ thống đã triển khai

### 5.8.1. Nguyên tắc tổ chức giao diện

Hệ thống đã triển khai giao diện trên ba môi trường: web dashboard cho nhân sự vận hành, Browser Extension cho thí sinh và cửa sổ OpenCV của desktop CV client. Mỗi môi trường được thiết kế theo nhiệm vụ của người sử dụng thay vì cố gắng gom tất cả chức năng vào một màn hình. Web dashboard ưu tiên quản trị, quan sát nhiều phiên và hậu kiểm; extension ưu tiên hướng dẫn từng bước, consent và trạng thái toàn vẹn trình duyệt; desktop client ưu tiên enrollment, liveness và phản hồi trực tiếp từ pipeline CV.

Giao diện web sử dụng shell Jinja2 thống nhất, tải dữ liệu động qua REST và nhận cập nhật realtime qua WebSocket. Menu, nút thao tác và tab được ẩn hoặc hiện theo capability để giảm nhầm lẫn thao tác. Đây chỉ là lớp hỗ trợ trải nghiệm: mọi request vẫn phải vượt qua authorization tại backend. Các trạng thái tải, rỗng, lỗi và mất kết nối được thể hiện riêng để người vận hành không hiểu nhầm dữ liệu cũ là dữ liệu đang cập nhật.

Các vị trí hình bên dưới chỉ ghi tiêu đề và nội dung cần chụp. Ảnh thật sẽ được bổ sung sau khi chạy hệ thống để bảo đảm phản ánh đúng phiên bản triển khai, dữ liệu mẫu và trạng thái giao diện tại thời điểm nghiệm thu.

### 5.8.2. Giao diện web dành cho quản trị và giám thị

**a) Đăng nhập và xác thực.** Trang đăng nhập tiếp nhận tài khoản nhân sự, hiển thị lỗi xác thực ở vùng trạng thái và chuyển sang bước MFA khi tài khoản hoặc vai trò yêu cầu. Sau khi thành công, backend thiết lập phiên đăng nhập bằng cookie HttpOnly; giao diện không tự lưu access token trong JavaScript.

> **Hình 5.1. Giao diện đăng nhập và xác thực người dùng**
> *Vị trí chèn ảnh chụp trang đăng nhập; nên thể hiện trường tài khoản, mật khẩu, thông báo trạng thái và bước MFA nếu có.*

**b) Quản trị nền tảng.** System overview tổng hợp số tổ chức, trạng thái vận hành và các lối tắt tới organization, policy, security và audit. Các trang con cho phép quản lý tổ chức, quota, chính sách mặc định, cấu hình bảo mật và tra cứu nhật ký. Dữ liệu evidence của thí sinh không xuất hiện mặc định trong phạm vi này.

> **Hình 5.2. Giao diện tổng quan quản trị nền tảng dành cho System Admin**
> *Vị trí chèn ảnh chụp trang System overview với thẻ thống kê và menu System Organizations, Policy, Security, Audit.*

**c) Quản trị tổ chức.** Organization overview hiển thị hồ sơ tổ chức, thành viên, invitation, trạng thái membership và các cấu hình áp dụng trong tenant. Organization Admin có thể thực hiện thao tác quản trị được cấp nhưng không mặc nhiên có quyền giám sát mọi kỳ thi. Các bảng có tìm kiếm, trạng thái rỗng và phản hồi kết quả thao tác.

> **Hình 5.3. Giao diện quản lý tổ chức, thành viên và quyền truy cập**
> *Vị trí chèn ảnh chụp Organization overview hoặc trang quản lý thành viên, trong đó thấy rõ vai trò và trạng thái membership.*

**d) Danh sách và không gian làm việc của kỳ thi.** Trang Exams chỉ tải các kỳ thi người dùng được phép xem. Exam overview cung cấp thông tin chung, trạng thái, mã tham gia và các tab theo capability. Exam Manager có thể chuyển sang tab quản lý; Proctor chủ yếu sử dụng dashboard và session detail.

> **Hình 5.4. Giao diện danh sách và không gian làm việc của kỳ thi**
> *Vị trí chèn ảnh chụp danh sách kỳ thi hoặc Exam overview, nên thể hiện trạng thái và mã tham gia.*

**e) Cấu hình và readiness.** Exam manage tập hợp policy của kỳ thi, phương thức xác thực thí sinh, thời gian mở/đóng, assignment và các điều kiện sẵn sàng. Màn hình giúp Exam Manager phát hiện cấu hình thiếu trước khi mở kỳ thi thay vì đợi đến khi thí sinh tham gia mới xử lý lỗi.

> **Hình 5.5. Giao diện cấu hình và kiểm tra trạng thái sẵn sàng của kỳ thi**
> *Vị trí chèn ảnh chụp tab Manage/Readiness với policy, assignment và kết quả kiểm tra trước khi mở kỳ thi.*

**f) Dashboard thời gian thực.** Dashboard hiển thị KPI, tình trạng WebSocket, bộ lọc phiên và bảng session. Mỗi phiên có trạng thái kết nối, risk hiện tại, integrity hiện tại, cảnh báo gần nhất và lối mở chi tiết. Dữ liệu khởi tạo được lấy qua REST, sau đó cập nhật bằng WebSocket ticket dùng một lần. Nếu socket gián đoạn, trạng thái kết nối phải cho giám thị biết dashboard có thể đang hiển thị dữ liệu cũ.

> **Hình 5.6. Dashboard giám sát các phiên thi theo thời gian thực**
> *Vị trí chèn ảnh chụp dashboard khi có nhiều phiên, KPI, bộ lọc và ít nhất một phiên có cảnh báo.*

**g) Chi tiết phiên và hậu kiểm.** Session detail tập trung thông tin thí sinh, trạng thái thiết bị, risk chart, timeline vi phạm, browser event, ảnh evidence và các thao tác review/report. Việc hiển thị contributing signals cùng timestamp và snapshot giúp giám thị hiểu nguyên nhân cảnh báo thay vì chỉ nhìn nhãn tổng hợp. Kết luận của người review được lưu tách khỏi sự kiện máy để bảo toàn dữ liệu gốc.

> **Hình 5.7. Giao diện chi tiết phiên thi, timeline và bằng chứng sự cố**
> *Vị trí chèn ảnh chụp Session detail có biểu đồ risk, danh sách violation/browser event và khu vực evidence.*

### 5.8.3. Giao diện Browser Extension dành cho thí sinh

Extension tổ chức luồng thiết lập theo các bước rõ ràng: kiểm tra mã tham gia; nhập thông tin hoặc đăng nhập Google; xem thông tin kỳ thi và policy; chạy preflight; xác nhận consent; sau đó mới tạo phiên. Các điều kiện chưa đạt được hiển thị ngay trong danh sách preflight để thí sinh biết cần cấp quyền hoặc thay đổi trạng thái nào.

> **Hình 5.8. Giao diện thiết lập Browser Extension trước khi tham gia kỳ thi**
> *Vị trí chèn ảnh chụp extension ở bước nhập mã, thông tin thí sinh, policy, preflight và consent.*

Khi phiên đã hoạt động, extension chuyển sang active card, hiển thị tóm tắt phiên và tình trạng các kênh giám sát. Người dùng có thể quay lại trang thi hoặc mở bảng giám sát; thao tác kết thúc phiên được đặt riêng và có ý nghĩa nghiệp vụ rõ ràng. Extension không cho tham gia một kỳ thi khác khi phiên hiện tại chưa kết thúc.

> **Hình 5.9. Giao diện trạng thái phiên đang hoạt động trên Browser Extension**
> *Vị trí chèn ảnh chụp active card với trạng thái sức khỏe, nút quay lại trang thi, mở bảng giám sát và kết thúc phiên.*

### 5.8.4. Giao diện desktop CV client

Desktop client dùng một cửa sổ OpenCV và điều khiển nội dung theo state của `AppController`. Ở trạng thái `IDLE`, người dùng nhập thông tin cần thiết để bắt đầu hoặc tham gia phiên. Ở `ENROLLMENT`, ứng dụng hướng dẫn đặt khuôn mặt vào vùng quan sát, thu đủ mẫu và thực hiện liveness. Chỉ khi enrollment thành công, pipeline mới chuyển sang `MONITORING`.

> **Hình 5.10. Giao diện Desktop CV tại bước nhập thông tin và bắt đầu phiên**
> *Vị trí chèn ảnh chụp trạng thái IDLE với trường thông tin, join code và hướng dẫn bắt đầu.*

> **Hình 5.11. Giao diện Desktop CV trong quá trình enrollment và liveness**
> *Vị trí chèn ảnh chụp khung camera, vùng căn chỉnh khuôn mặt, tiến độ thu mẫu và hướng dẫn liveness.*

Trong `MONITORING`, frame hiển thị được phủ thông tin trạng thái phiên, FPS, risk score và các tín hiệu cần giải thích. Violation được tạo theo rising edge nên giao diện không phát sinh một cảnh báo mới ở mọi frame. Khi kết thúc, ứng dụng chuyển qua `GENERATING_REPORT` rồi `ENDED`, đồng thời đóng tài nguyên camera và hoàn thiện log/report cục bộ.

> **Hình 5.12. Giao diện Desktop CV trong quá trình giám sát**
> *Vị trí chèn ảnh chụp trạng thái MONITORING có khung camera, risk score và trạng thái các signal.*

### 5.8.5. Giao diện evidence và báo cáo

Sau phiên thi, giám thị có thể yêu cầu report job. Worker đọc metadata và các file evidence, tổng hợp thống kê, dựng biểu đồ rồi xuất HTML/PDF. Báo cáo phân biệt cảnh báo CV, sự kiện trình duyệt và kết luận review; ảnh chỉ được đọc từ đường dẫn nằm trong thư mục phiên đã được server kiểm soát.

> **Hình 5.13. Giao diện xem xét evidence và ghi nhận kết luận của giám thị**
> *Vị trí chèn ảnh chụp khu vực review với evidence, verdict và ghi chú của người đánh giá.*

> **Hình 5.14. Báo cáo HTML/PDF được sinh sau phiên thi**
> *Vị trí chèn ảnh chụp trang đầu báo cáo và một trang có timeline, bảng vi phạm hoặc ảnh bằng chứng.*

### 5.8.6. Luồng vận hành đầu-cuối

Luồng dữ liệu kỹ thuật đã được trình bày tại Hình 4.9; ở góc nhìn vận hành, một kỳ thi đi qua các bước sau:

1. System Admin hoặc Organization Admin chuẩn bị tổ chức, thành viên, quota và policy theo đúng phạm vi.
2. Exam Manager tạo kỳ thi, cấu hình phương thức xác thực, policy giám sát, thời gian và assignment; sau đó kiểm tra readiness trước khi mở.
3. Candidate nhập join code trên extension hoặc desktop client. Backend kiểm tra mã, thời hạn, trạng thái kỳ thi và trả về policy hiệu lực.
4. Candidate xác thực, cấp consent và hoàn tất preflight. Desktop client thực hiện enrollment/liveness; extension kiểm tra các quyền trình duyệt cần thiết.
5. Khi phiên hoạt động, desktop client gửi telemetry/violation, extension gửi browser event/heartbeat. Backend kiểm tra session token, schema, sequence và đối chiếu dữ liệu dẫn xuất.
6. Dashboard nạp trạng thái ban đầu từ REST, dùng ticket ngắn hạn để mở WebSocket và nhận cập nhật đã kiểm chứng. Proctor lọc phiên, mở session detail và xem evidence khi cần.
7. Khi phiên kết thúc, backend chốt trạng thái; giám thị thực hiện review, Exam Manager hoặc người có capability yêu cầu sinh report. Worker tổng hợp dữ liệu thành HTML/PDF và lưu kết quả gắn với phiên.

Mỗi bước tạo ra một trạng thái quan sát được trên giao diện. Điều này giúp xác định lỗi nằm ở cấu hình kỳ thi, xác thực, thiết bị thí sinh, kết nối realtime, pipeline giám sát hay reporting, thay vì chỉ báo một lỗi chung cho toàn hệ thống.

### 5.8.7. Luồng lỗi và chế độ suy giảm

Hệ thống xử lý một số tình huống không thuận lợi theo hướng bảo toàn bằng chứng và thông báo rõ trạng thái:

- Join code sai, hết hạn hoặc kỳ thi chưa mở bị từ chối trước khi tạo phiên.
- Thiếu camera, quyền trình duyệt hoặc consent làm preflight chưa đạt; giao diện chỉ rõ điều kiện cần sửa.
- Message WebSocket sai schema, thiếu signal, sequence trùng hoặc timestamp không hợp lệ bị server từ chối và không phát tán sang dashboard.
- Dashboard mất WebSocket hiển thị trạng thái ngắt kết nối; dữ liệu khởi tạo có thể được tải lại qua REST sau khi kết nối phục hồi.
- Desktop client mất backend vẫn có thể tiếp tục pipeline và log cục bộ theo chế độ best-effort; tuy nhiên dashboard không được coi là realtime trong khoảng gián đoạn.
- Report job lỗi chuyển sang `failed` và lưu thông báo lỗi thay vì tạo một báo cáo không hoàn chỉnh dưới trạng thái thành công.
- Retention job mặc định chạy dry-run để người vận hành xem phạm vi dữ liệu trước khi áp dụng xóa hoặc ẩn danh.

## 5.9. Lưu trữ evidence và sinh báo cáo

### 5.9.1. Materialize thư mục phiên

`session_materializer.py` chỉ cho phép append vào năm file JSONL đã định nghĩa: `signals`, `violations`, `risk_score_timeline`, `state_transitions` và `browser_events`. Thư mục snapshot được tạo dưới đúng session ID do server quản lý.

Ảnh upload phải là JPEG/PNG, tối đa 2 MiB và không vượt giới hạn pixel. Module decode base64, so khớp hash, kiểm tra magic bytes bằng Pillow và ghi tệp tạm trước khi replace. Event ID được lọc ký tự và giới hạn độ dài để ngăn path traversal.

### 5.9.2. Reporting pipeline

`data_loader.py` đọc từng file theo kiểu tolerant: file thiếu hoặc dòng trống trả dữ liệu rỗng thay vì làm hỏng cả báo cáo. `aggregator.py` tính thời lượng, số vi phạm, severity, snapshot và peak risk. `charts.py` vẽ timeline risk và phân bố violation. `report_generator.py` render Jinja2 HTML và dùng xhtml2pdf để tạo PDF có tiếng Việt.

Browser event và risk CV được trình bày tách biệt trong báo cáo. Đường dẫn ảnh phải được resolve nằm trong thư mục session; report không đọc đường dẫn tùy ý từ log.

### 5.9.3. Report job và retention

API tạo `ReportJob`; `scripts/report_worker.py` lấy job pending, chuyển trạng thái và ghi output/error. Docker Compose chạy worker riêng để request web không bị chặn bởi quá trình dựng PDF.

`scripts/cleanup_retention.py` mặc định dry-run. Chế độ apply xử lý evidence, review/report liên quan và ẩn danh row phiên theo policy, đồng thời ghi audit. Thiết kế yêu cầu người vận hành xem danh sách trước khi xóa dữ liệu vật chất.

## 5.10. Triển khai

### 5.10.1. Chạy cục bộ

Desktop CV được chạy bằng:

```bash
python main.py
```

Nếu chỉ cần demo cục bộ, `backend.enabled` giữ `false`. Khi kết nối nền tảng, bật tùy chọn này và cấu hình `base_url/ws_url`.

Backend phát triển có thể dùng Uvicorn và SQLite. Các secret/OAuth setting được đọc từ biến môi trường; `.env.example` mô tả biến cần thiết. Production từ chối secret hoặc mật khẩu mặc định không an toàn.

### 5.10.2. Docker Compose

`docker-compose.yml` dựng bốn service:

| Service | Vai trò |
|---|---|
| `db` | PostgreSQL 16 và volume `db_data` |
| `redis` | Redis 7 với append-only persistence |
| `backend` | FastAPI/Uvicorn, port 8000 và volume evidence |
| `report-worker` | Xử lý report job dùng cùng database/evidence volume |

`Dockerfile.backend` dựa trên Python 3.11 slim và chỉ cài dependency backend. Database/evidence dùng volume để không mất dữ liệu khi container restart.

### 5.10.3. Migration và tương thích

`db_migrations.py` tạo/bổ sung bảng và cột theo các migration marker, đồng thời backfill nền tảng RBAC. `User.org_id/User.role` cũ vẫn được dual-write trong giai đoạn tương thích, nhưng quyết định quyền mới đọc `OrganizationMembership`, `SystemRole` và `ExamAssignment`.

Migration nội bộ hiện được viết bằng SQLAlchemy/SQL thay vì một framework migration độc lập như Alembic. Điều này phù hợp giai đoạn đồ án nhưng cần được chuẩn hóa thêm nếu phát triển nhiều nhánh release và rollback phức tạp.

## 5.11. Các quyết định cài đặt đáng chú ý

| Vấn đề | Quyết định cài đặt |
|---|---|
| Detector nặng | Dùng chung `PerceptionResult`; throttle YOLO |
| Nhiễu từng frame | Debounce/cửa sổ thời gian và state machine độc lập |
| Log cảnh báo bị trùng | Chỉ sinh violation ở rising edge |
| Mất landmark | Trả confidence 0; không nhân bản vi phạm sang signal khác |
| Mất backend | Desktop tiếp tục local; gửi mạng best-effort |
| Client không tin cậy | Schema chặt, server timestamp và tính/đối chiếu dữ liệu dẫn xuất |
| Token WebSocket browser | Ticket ngắn hạn, dùng một lần |
| Truy cập chéo tenant | Authorization tập trung theo membership/assignment |
| Dữ liệu trạng thái và timeline khác tải | SQL cho current state; JSONL cho append-only evidence |
| Sinh PDF có thể chậm | Report job và worker nền |

## 5.12. Kết chương

Chương 5 đã mô tả implementation thực tế của desktop CV, browser extension, backend FastAPI, dashboard, lớp dữ liệu và quy trình triển khai. Phần giao diện cho thấy các chức năng đã được ánh xạ thành luồng thao tác riêng cho quản trị viên, Exam Manager, giám thị và thí sinh; các vị trí chèn ảnh đã được chuẩn bị để bổ sung screenshot từ hệ thống chạy thật. Các thành phần được liên kết bằng data contract thay vì phụ thuộc trực tiếp vào implementation của nhau. Cấu hình tập trung, authorization tập trung và validation phía server giúp giảm sai lệch giữa thiết kế, giao diện và hành vi thực thi.

Chương 6 tiếp theo trình bày kiểm thử source code hiện tại và kết quả thực nghiệm trên bộ 25 video ở môi trường đánh giá riêng, đồng thời phân biệt rõ bằng chứng phần mềm với bằng chứng về độ chính xác CV.
