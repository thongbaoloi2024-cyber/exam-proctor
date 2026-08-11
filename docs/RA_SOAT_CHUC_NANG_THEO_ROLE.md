# Rà soát chức năng theo role và đề xuất hoàn thiện hệ thống

Ngày rà soát: 2026-08-11

## 1. Phạm vi và kết luận nhanh

Phạm vi rà soát gồm RBAC/tenant/resource scope ở backend, các route và API,
giao diện Jinja2/JavaScript, dashboard giám thị và browser extension dành cho
thí sinh.

Hệ thống đã có nền tảng phân quyền tốt ở tầng backend: `system_admin`,
`org_admin`, `exam_manager`, ba mức assignment `owner/manager/proctor`, và token
thí sinh tách biệt. Các kiểm tra tenant/resource scope, quyền truy cập ngoại lệ và thu hồi
phiên đã được thiết kế tập trung trong `backend/authorization.py`.

Khoảng trống lớn nhất hiện không nằm ở mô hình role, mà ở việc quyền và chính
sách chưa được phản ánh đầy đủ trên từng tài nguyên/màn hình. Một số API đã có
nhưng không có giao diện sử dụng; một số giao diện dùng capability tổng hợp của
toàn tài khoản nên hiển thị hành động sai trên từng kỳ thi; chính sách tổ chức
được lưu nhưng chưa được kế thừa/enforce khi tạo kỳ thi.

## 2. Ma trận chức năng hiện tại

| Role/phạm vi | Chức năng đã có | Điểm còn thiếu chính |
|---|---|---|
| `system_admin` | Dashboard platform; danh sách/chi tiết tổ chức; tạo, khóa/mở, quota và retention; nhật ký hoạt động toàn cục; yêu cầu quyền truy cập ngoại lệ; evidence chỉ đọc sau phê duyệt; bắt buộc MFA | Chưa có trang vận hành/health/worker/storage/report queue; chưa có chính sách sàn toàn hệ thống, feature flag và version policy; chưa quản lý vòng đời Organization Admin; chưa có re-auth cho thao tác nhạy cảm; security center chưa tổng hợp đăng nhập lỗi/rate limit |
| `org_admin` | Xem/cập nhật thành viên; mời và đổi role/status; chính sách tổ chức; duyệt/thu hồi quyền truy cập ngoại lệ; nhật ký hoạt động của tổ chức | Chưa có overview usage/quota; chưa hiển thị và thu hồi lời mời đang chờ; form chính sách thiếu nhiều trường và có thể ghi đè ngầm; chính sách chưa áp dụng vào kỳ thi; thiếu thông tin người yêu cầu khi duyệt quyền truy cập ngoại lệ; chưa có UI đổi tên/cài đặt tổ chức; bộ chuyển tổ chức bị ẩn |
| `exam_manager` + `owner/manager` | Tạo/list kỳ thi theo assignment; lifecycle; phân công; dashboard realtime; evidence, incident review, report | Capability frontend chưa theo từng kỳ thi; trang sửa draft chỉ có tên/lịch; thiếu readiness checklist, roster thí sinh, bộ lọc dashboard, incident queue và report job UI; quick action lifecycle chưa phản ánh đúng trạng thái; thiếu expiry/ca trực trong phân công |
| `exam_manager` + `proctor` | Theo dõi dashboard, xem evidence, review incident, export report và API kết thúc phiên | UI chưa có nút kết thúc phiên; chưa hiển thị last-seen/disconnect reason; cảnh báo không được ưu tiên/sắp xếp; có thể thấy nhầm nút quản lý nếu tài khoản là manager ở kỳ thi khác |
| Thí sinh/extension | Kiểm tra join code; manual/Google auth; consent; kiểm tra camera/mic; monitor camera/screen/fullscreen/clipboard; reconnect WebSocket; tự kết thúc phiên | Phiên đang chạy chỉ có thông báo, không có nút quay lại tab/kết thúc; chưa có luồng khôi phục khi mất local state hoặc đổi thiết bị; chưa có preflight theo từng bước và hướng dẫn xử lý lỗi; chưa hiển thị trạng thái đồng bộ/offline queue rõ ràng |

## 3. Các phát hiện cần xử lý

### P0 — sai lệch quyền/chính sách hoặc chặn chức năng đã công bố

#### P0.1. Hành động frontend không theo quyền của từng kỳ thi

`capabilities_for_user()` hợp nhất capability của mọi assignment của tài khoản.
Ví dụ, một người là `manager` ở kỳ thi A và `proctor` ở kỳ thi B sẽ có capability
`exam.manage` ở `/auth/me`. `exams.js` dùng capability toàn cục này để hiện nút
Quản lý/Mở/Đóng/Đổi mã cho mọi dòng. Backend vẫn chặn đúng ở kỳ thi B, nhưng
người dùng nhận nút không hợp lệ rồi gặp 403.

Đề xuất:

- Trả về `assignment_role` và `allowed_actions`/`capabilities` trên từng
  `ExamResponse`.
- Dựng action của từng dòng từ quyền resource-level này.
- Dùng cùng dữ liệu để bảo vệ trang manage, lifecycle, assignment và dashboard.
- Thêm test cho tài khoản đồng thời là manager ở A và proctor ở B.

#### P0.2. Chính sách tổ chức chưa được kế thừa/enforce và có thể bị ghi đè ngầm

API lưu đủ `default_candidate_auth_mode`, camera, microphone, screen share,
fullscreen, clipboard, extension version và focus threshold. Tuy nhiên form UI
chỉ hiển thị một phần. Khi lưu, JavaScript luôn gửi `manual`, microphone=false,
screen-share=false và clipboard=true, dù giá trị trước đó là gì. Ngoài ra API
tạo kỳ thi không đọc chính sách tổ chức, nên Exam Manager có thể tạo cấu hình
yếu hơn “chính sách mặc định” và form tạo kỳ thi luôn dùng giá trị hard-coded.

Đề xuất:

- Hiển thị toàn bộ trường chính sách và không hard-code trường bị ẩn khi PUT.
- Phân biệt rõ `default` và `minimum/enforced`; backend phải merge và validate,
  không chỉ dựa vào frontend.
- Khi tạo kỳ thi, trả về policy đã resolve gồm `system floor → organization
  policy → exam override` và nêu trường nào bị khóa.
- Ghi policy snapshot vào kỳ thi/phiên để truy vết được cấu hình thực tế.
- Thêm regression test chứng minh không thể hạ policy bắt buộc.

#### P0.3. Duyệt quyền truy cập ngoại lệ thiếu ngữ cảnh để ra quyết định an toàn

Trang Organization Admin hiện chỉ hiển thị lý do, trạng thái và hết hạn. API có
`requester_user_id`, `scope`, `read_only`, `created_at` nhưng UI không hiển thị;
response cũng không có email người yêu cầu. Organization Admin vì vậy không biết
rõ đang cấp quyền cho ai và phạm vi cụ thể nào.

Đề xuất:

- Trả về và hiển thị requester email/tên, scope, read-only, thời điểm tạo, thời
  lượng, thời điểm hết hạn và trạng thái hiệu lực tính toán.
- Modal phê duyệt phải hiển thị toàn bộ phạm vi, yêu cầu nhập lý do/ghi chú và
  xác thực lại người duyệt.
- Thông báo cho các Organization Admin khi yêu cầu được tạo, kích hoạt, sắp hết
  hạn và bị thu hồi.
- Ghi nhật ký cả lần xem evidence và lần tải report theo grant cụ thể.

#### P0.4. Multi-organization đã có API nhưng không sử dụng được từ UI

`API.loadOrganizationSwitcher()` và endpoint đổi active organization đã có,
nhưng khối HTML `organization-context` trong sidebar đang bị comment. Người dùng
thuộc nhiều tổ chức không có cách đổi context từ giao diện.

Đề xuất: bật lại organization switcher, hiển thị rõ tên tổ chức + role đang
hoạt động, xác nhận khi đổi context nếu đang có form chưa lưu và test việc menu/
capability được tải lại sau khi đổi.

#### P0.5. Quick action lifecycle hiển thị hành động không hợp lệ

Danh sách kỳ thi dùng quy tắc đơn giản: đang `open` thì hiện “Đóng”, mọi trạng
thái khác hiện “Mở”, đồng thời luôn hiện “Đổi mã” khi có capability manage. Vì
vậy kỳ thi `archived` vẫn thấy Mở/Đổi mã dù API từ chối. Quick action cũng không
gửi `expected_version`, nên bỏ qua optimistic locking đang có ở trang manage.

Đề xuất: backend trả `allowed_transitions`; frontend chỉ render transition hợp
lệ, dùng `expected_version`, thêm xác nhận cho đóng/lưu trữ/đổi mã và không để
rotate code tự thay đổi lifecycle ngoài ý muốn.

### P1 — hoàn thiện công việc chính của từng role

#### System Admin

1. Thêm Operations Center: health backend/DB/Redis, worker/report queue,
   storage usage, lỗi gần đây, version extension/client và cảnh báo quota.
2. Thêm System Policy: minimum extension version, MFA requirement cho
   Organization Admin, retention floor/ceiling, feature flags và security floor.
3. Thêm quản lý Organization Admin: mời bổ sung, thu hồi, khóa session và bảo vệ
   trường hợp admin cuối cùng.
4. Mở rộng Security Center với failed login, account lock, rate-limit event,
   bất thường token/WebSocket và bộ lọc theo IP/request ID.
5. Yêu cầu recent MFA/re-auth cho suspend tenant, đổi quota lớn, cấp quyền nhạy
   cảm hoặc xem evidence bằng quyền truy cập ngoại lệ.

#### Organization Admin

1. Thêm overview tổ chức: người dùng active/suspended, quota, storage/retention,
   mức tuân thủ policy và lời mời chờ xử lý.
2. Hiển thị danh sách invitation (API list/revoke đã có), trạng thái, expiry,
   resend/copy link và revoke.
3. Thêm cài đặt tổ chức: tên, logo, timezone, domain email, contact và cấu hình
   Google Workspace mặc định.
4. Giao diện nhật ký hoạt động cần search/filter/pagination, actor, reason, request ID và before/
   after giống System Admin.
5. Thêm yêu cầu export/xóa dữ liệu và tiến trình phê duyệt theo retention.
6. Thêm chính sách MFA/force logout và trang security posture của thành viên.

#### Exam owner/manager

1. Chuyển form tạo kỳ thi thành wizard: thông tin → lịch → xác thực → thiết bị →
   giám sát → nhân sự → rà soát. Khởi tạo từ policy tổ chức đã resolve.
2. Cho sửa đầy đủ cấu hình ở draft. Hiện tại UI chỉ sửa tên và lịch dù API đã
   hỗ trợ phần lớn trường; auth mode và Google domain còn chưa có update API.
3. Thêm Exam Overview/readiness checklist: lịch hợp lệ, join code còn hạn,
   extension/OAuth sẵn sàng, đủ proctor, quota, số thí sinh và lỗi thiết bị.
4. Thêm candidate roster với trạng thái join/auth/device, tìm kiếm và khả năng
   reset/reissue một phiên lỗi có ghi nhật ký.
5. Bổ sung assignment expiry/ca trực, nhãn role tiếng Việt, chuyển owner theo
   quy trình xác nhận và cảnh báo khi kỳ thi không còn proctor.
6. Cho chọn TTL khi tạo/rotate join code; hiển thị countdown và cảnh báo sắp hết
   hạn. Hiện rotate luôn đặt 24 giờ.

#### Proctor/giám thị

1. Dashboard cần tìm kiếm, lọc trạng thái, lọc cảnh báo, sắp xếp ưu tiên theo
   alert/integrity/risk/last-seen và giữ alert ở đầu bảng.
2. Hiển thị `last_seen_at`, `disconnect_reason`, thời gian mất kết nối, phiên bản
   extension/browser và trạng thái camera/mic/screen-share.
3. Thêm action kết thúc phiên với modal xác nhận/lý do; backend endpoint đã có
   nhưng UI chưa gọi.
4. Tạo incident review queue riêng: lọc new/in-review, claim người xử lý, bulk
   dismiss/confirm có kiểm soát, attribution và lịch sử thay đổi.
5. Hiển thị timeline hợp nhất CV + browser event, marker trên biểu đồ, bộ lọc
   severity/type và xem ảnh trong modal thay vì mở blob tab mới.
6. Dùng report job nền đã có, hiển thị pending/processing/failed/completed và
   link tải hết hạn; không gọi sinh PDF đồng bộ từ UI.

#### Thí sinh/extension

1. Active session card cần nút “Quay lại trang thi”, “Mở bảng giám sát” và “Kết
   thúc phiên” có xác nhận.
2. Preflight theo từng bước: version, quyền backend/exam origin, camera, mic,
   screen share, fullscreen, clock drift và network; mỗi lỗi có hướng dẫn sửa.
3. Thiết kế resume/rejoin an toàn khi extension mất local state, đổi thiết bị
   hoặc trình duyệt crash. Hiện unique identity/candidate number chặn mọi lần
   join sau khi đã có session, kể cả phiên lỗi.
4. Hiển thị trạng thái WebSocket, lần đồng bộ cuối, số event đang chờ và cảnh báo
   khi offline queue gần đầy.
5. Hiển thị mã hỗ trợ/session rút gọn để thí sinh cung cấp cho giám thị mà không
   lộ token; thêm trang kết thúc xác nhận dữ liệu đã gửi.

### P2 — mở rộng sản phẩm và trải nghiệm

- Nhóm/khoa/phòng ban, cohort và template kỳ thi dùng lại.
- Lịch thi dạng calendar và thông báo trước ca trực.
- Báo cáo tổng hợp không định danh theo tổ chức/kỳ thi, so sánh xu hướng và SLA
  xử lý incident.
- Notification center/email/webhook cho quyền truy cập ngoại lệ, quota, phiên mất kết nối,
  join-code expiry và report hoàn tất.
- Branding, đa ngôn ngữ, timezone theo tổ chức và đánh giá accessibility đầy đủ.
- Export CSV/PDF theo bộ lọc, watermark, signed URL ngắn hạn và data-subject
  request workflow.

## 4. Thứ tự triển khai khuyến nghị

### Đợt 1 — sửa độ đúng của quyền và policy

1. Per-exam allowed actions/capabilities.
2. Full organization policy UI + backend policy resolution/enforcement.
3. Ngữ cảnh phê duyệt quyền truy cập ngoại lệ + re-auth.
4. Bật multi-org switcher.
5. Lifecycle actions theo `allowed_transitions` và optimistic locking.

### Đợt 2 — hoàn thiện vận hành kỳ thi

1. Exam wizard và trang draft đầy đủ.
2. Dashboard filter/sort/last-seen + force-end.
3. Candidate roster và recovery/rejoin.
4. Incident queue và report job UI.

### Đợt 3 — hoàn thiện quản trị platform/tenant

1. Organization overview, invitation list, settings và nhật ký hoạt động nâng cao.
2. System Operations Center và System Policy.
3. Notification/security event center và data lifecycle workflow.

## 5. Kiểm thử cần bổ sung

- Permission snapshot theo từng `exam_id`, không chỉ capability union của user.
- UI test cho manager ở kỳ thi A/proctor ở B và archived lifecycle.
- Policy resolution test cho system floor, org policy và exam override.
- Regression test đảm bảo form policy không làm đổi trường không hiển thị.
- Kiểm thử phê duyệt/chi tiết/nhật ký quyền truy cập ngoại lệ gắn với requester và grant ID.
- Multi-org switch test kiểm tra cookie/JWT, menu và scope sau chuyển context.
- Resume/rejoin test sau crash/mất local state và chống duplicate/replay.
- Dashboard test cho force-end, sorting alert, disconnected state và report job.

## 6. Trạng thái xác minh

- Đã rà soát tĩnh code backend, frontend, extension, tài liệu RBAC và các test
  hiện có.
- Extension test: 6/6 test pass bằng `npm test`.
- Chưa chạy được backend test trong môi trường hiện tại vì Python đang dùng chưa
  cài package `pytest`; đây là giới hạn môi trường, không phải kết luận test fail.
- Không thay đổi mã nguồn chức năng trong đợt rà soát này.
