# Kiến trúc quản trị và phân quyền

> **Trạng thái cập nhật 2026-08-03:** các giai đoạn nền tảng RBAC, membership,
> phân công, quản trị tổ chức/kỳ thi, quản trị hệ thống, nhật ký hoạt động, quyền truy cập ngoại lệ, MFA và
> giao diện theo capability đã được triển khai. `User.org_id`/`User.role` vẫn
> được giữ để tương thích trong giai đoạn migration. Redis đã phục vụ rate
> limit, WebSocket pub/sub và distributed client lease; report worker, quota và
> retention job cũng đã có. Object storage và PostgreSQL RLS vẫn là hardening
> tùy chọn tiếp theo; local/shared volume vẫn là storage mặc định.

## 1. Mục tiêu và nguyên tắc

Hệ thống cần hỗ trợ ba mức quản trị:

1. **Quản trị hệ thống** (`system_admin`): vận hành toàn nền tảng và quản lý tổ chức.
2. **Quản trị tổ chức** (`org_admin`): quản trị một tổ chức, người dùng và
   chính sách của tổ chức đó.
3. **Quản lý kỳ thi/Giáo viên** (`exam_manager`): tạo hoặc vận hành các kỳ thi
   được giao, theo dõi thí sinh và xử lý báo cáo.

Thí sinh không thuộc hệ thống vai trò quản trị. Thí sinh tiếp tục dùng token
`exam_session` chỉ có hiệu lực với đúng một phiên thi.

Thiết kế áp dụng đồng thời ba lớp kiểm tra:

- **RBAC**: vai trò xác định nhóm hành động được phép.
- **Tenant scope**: `org_id` giới hạn dữ liệu trong một tổ chức.
- **Resource scope**: `ExamAssignment` giới hạn giáo viên vào các kỳ thi được
  phân công.

Không xem vai trò là một chuỗi quyền kế thừa tuyệt đối. Đặc biệt, System Admin
quản lý hạ tầng nhưng không mặc định được đọc ảnh bằng chứng, danh tính hay báo
cáo chi tiết của thí sinh.

## 2. Ranh giới vai trò

### 2.1. Quản trị hệ thống

Phạm vi: toàn nền tảng, không gắn cố định với một `org_id`.

Chức năng chính:

- Xem dashboard vận hành: số tổ chức, người dùng, kỳ thi đang mở, phiên đang
  hoạt động, dung lượng và lỗi hệ thống.
- Tạo, khóa, mở khóa và cấu hình hạn mức tổ chức.
- Mời hoặc thu hồi quản trị tổ chức đầu tiên của một tổ chức.
- Quản lý cấu hình toàn cục, phiên bản extension tối thiểu, feature flag và
  chính sách bảo mật bắt buộc.
- Xem nhật ký hoạt động toàn hệ thống và sự kiện an ninh.
- Thực hiện tác vụ hỗ trợ có kiểm soát.

Không được mặc định:

- Tham gia vận hành kỳ thi thay giáo viên.
- Xem ảnh, timeline hoặc báo cáo chứa dữ liệu cá nhân của thí sinh.
- Sửa điểm rủi ro, vi phạm hoặc nhật ký hoạt động.

Khi cần hỗ trợ dữ liệu nhạy cảm, dùng **quyền truy cập ngoại lệ**: nhập lý do, xác
thực lại, giới hạn thời gian, chỉ đọc, thông báo cho quản trị tổ chức và ghi
nhật ký đầy đủ.

### 2.2. Quản trị tổ chức

Phạm vi: một tổ chức đang được chọn.

Chức năng chính:

- Xem thông tin, thành viên, chính sách và mức sử dụng của tổ chức.
- Mời, khóa, mở khóa người dùng; gán hoặc thu hồi vai trò `org_admin` và
  `exam_manager` trong tổ chức.
- Thiết lập chính sách mặc định: xác thực thí sinh, thiết bị bắt buộc, thời hạn
  lưu dữ liệu, ngưỡng cảnh báo và phiên bản extension tối thiểu.
- Xem nhật ký hoạt động quản trị và mức sử dụng của tổ chức.
- Duyệt yêu cầu xuất hoặc xóa dữ liệu theo chính sách.

Không được:

- Đọc hoặc sửa dữ liệu của tổ chức khác.
- Tạo `system_admin` hay thay đổi cấu hình toàn platform.
- Tạo, đọc, sửa, phân công, giám sát hoặc xuất dữ liệu kỳ thi; assignment lịch
  sử không cấp lại các quyền này.
- Sửa/xóa nhật ký hoạt động.
- Hạ chính sách dưới mức tối thiểu do System Admin bắt buộc.

### 2.3. Quản lý kỳ thi/Giáo viên

Phạm vi: các kỳ thi do mình tạo hoặc được ghi trong `ExamAssignment`.

Chức năng chính:

- Xem danh sách **Kỳ thi của tôi**.
- Tạo kỳ thi; người tạo tự động trở thành `owner` của kỳ thi.
- Chỉnh cấu hình khi kỳ thi ở `draft`; mở/đóng kỳ thi và xoay mã tham gia nếu
  được giao quyền `owner` hoặc `manager`.
- Chọn đồng nghiệp đã tồn tại trong tổ chức để cùng coi thi; không tự tạo tài
  khoản hay nâng vai trò tổ chức.
- Xem dashboard thời gian thực, kết thúc phiên lỗi, ghi chú/đánh dấu sự cố,
  duyệt bằng chứng và xuất báo cáo của kỳ thi được giao.
- Xem dữ liệu thí sinh ở mức tối thiểu cần cho công việc.

Không được:

- Xem kỳ thi không được phân công, kể cả biết `exam_id`.
- Quản lý người dùng, chính sách, hạn mức hoặc nhật ký hoạt động toàn tổ chức.
- Chuyển kỳ thi sang tổ chức khác, thay đổi retention hoặc xóa bằng chứng trước
  hạn.
- Cấp cho người khác quyền cao hơn quyền mình có trên kỳ thi.

Trong một kỳ thi, `ExamAssignment.assignment_role` có ba mức nhỏ:

- `owner`: toàn quyền vận hành kỳ thi và quản lý phân công.
- `manager`: chỉnh cấu hình, mở/đóng, quản lý phiên và báo cáo.
- `proctor`: chỉ theo dõi trực tiếp, xem chi tiết và xử lý phiên trong ca được giao.

Ba mức này là phạm vi tài nguyên, không phải vai trò platform mới.

## 3. Ma trận quyền mục tiêu

Ký hiệu: **Toàn hệ thống**, **Trong tổ chức**, **Kỳ thi được giao**, và `—` là
không được phép.

| Nhóm chức năng | System Admin | Organization Admin | Exam Manager/Giáo viên |
|---|---:|---:|---:|
| Quản lý tổ chức, trạng thái, hạn mức | Toàn hệ thống | Xem tổ chức của mình | — |
| Gán System Admin | Theo quy trình bảo mật riêng | — | — |
| Quản lý thành viên/vai trò | Admin tổ chức | Trong tổ chức | — |
| Cấu hình chính sách mặc định | Mức sàn toàn cục | Trong tổ chức | — |
| Tạo kỳ thi | Hỗ trợ có ghi nhật ký | — | Tự tạo và được gán owner |
| Xem danh sách kỳ thi | Metadata vận hành | — | Kỳ thi được giao |
| Sửa/mở/đóng kỳ thi | Hỗ trợ có ghi nhật ký | — | Theo assignment |
| Phân công giáo viên/giám thị | Hỗ trợ có ghi nhật ký | — | Người dùng có sẵn, theo assignment |
| Theo dõi dashboard live | Không mặc định | — | Kỳ thi được giao |
| Xem ảnh/báo cáo thí sinh | Quyền truy cập ngoại lệ, chỉ đọc | — | Kỳ thi được giao |
| Kết thúc một phiên thi | — | — | Kỳ thi được giao |
| Ghi chú/duyệt sự cố | — | — | Kỳ thi được giao |
| Xuất báo cáo | Thống kê không định danh | — | Kỳ thi được giao |
| Xóa dữ liệu trước retention | Quy trình hệ thống | Theo quy trình phê duyệt | — |
| Xem nhật ký hoạt động | Toàn hệ thống | Trong tổ chức | Hành động của mình/kỳ thi được giao |

Quy tắc phủ định luôn thắng quyền tổng quát: tài khoản `suspended`, tổ chức
`suspended`, kỳ thi đã `archived`, assignment hết hạn hoặc chính sách deny cụ
thể phải chặn hành động dù vai trò thông thường cho phép.

## 4. Sitemap và giao diện quản trị

### 4.1. Khung giao diện chung

Thanh điều hướng phải được dựng từ quyền backend trả về, không chỉ từ chuỗi
`role` lưu ở `sessionStorage`:

- Logo, tên tổ chức đang hoạt động và môi trường triển khai.
- Menu theo quyền; ẩn mục không liên quan nhưng backend vẫn kiểm tra lại mọi API.
- Badge vai trò và phạm vi hiện tại.
- Thông báo sự kiện quan trọng, menu hồ sơ, đổi mật khẩu và đăng xuất.
- Breadcrumb luôn hiển thị `Tổ chức → Kỳ thi → Phiên thi` để hạn chế thao tác
  nhầm phạm vi.

Nếu một người thuộc nhiều tổ chức, họ phải chọn **active organization**. Việc
đổi tổ chức tạo context mới phía server; không tin `org_id` tùy ý do frontend
gửi trong body.

### 4.2. Giao diện quản trị hệ thống

Đường dẫn đề xuất dưới `/ui/system`:

| Màn hình | Nội dung/chức năng |
|---|---|
| Tổng quan | Chỉ số toàn nền tảng, tổ chức/phiên đang hoạt động, lỗi, dung lượng, phiên bản tiện ích |
| Tổ chức | Tìm, lọc, tạo hoặc khóa tổ chức; cấu hình hạn mức, thời hạn lưu trữ và trạng thái |
| Chi tiết tổ chức | Thông tin, mức sử dụng, quản trị viên và lịch sử thay đổi; không mở dữ liệu thí sinh theo mặc định |
| Quản trị viên | Mời hoặc thu hồi quản trị tổ chức, khóa phiên đăng nhập |
| Chính sách hệ thống | Mức bảo mật tối thiểu, cờ tính năng và chính sách phiên bản |
| Vận hành | Tình trạng dịch vụ, tiến trình xử lý, cơ sở dữ liệu, kho lưu trữ, hàng đợi báo cáo và cảnh báo |
| Nhật ký & Bảo mật | Tìm kiếm nhật ký hoạt động, đăng nhập lỗi, rate limit, phiên truy cập ngoại lệ |

Các thao tác `suspend organization`, đổi hạn mức hoặc cấp quyền truy cập ngoại lệ cần modal xác
nhận, nhập lý do và xác thực lại.

### 4.3. Giao diện quản trị tổ chức

Đường dẫn đề xuất dưới `/ui/org`:

| Màn hình | Nội dung/chức năng |
|---|---|
| Tổng quan tổ chức | Usage, trạng thái chính sách và người dùng |
| Người dùng | Danh sách, mời mới, vai trò, trạng thái, đăng xuất cưỡng bức |
| Nhóm/đơn vị | Nhóm giáo viên hoặc khoa/phòng nếu tổ chức cần phân cấp thêm |
| Chính sách | Mẫu cấu hình kỳ thi, xác thực, tiện ích trình duyệt, thời hạn lưu trữ và quyền riêng tư |
| Báo cáo | Thống kê tổng hợp, xuất dữ liệu theo phạm vi và thời gian |
| Nhật ký hoạt động | Hoạt động quản trị và truy cập dữ liệu trong tổ chức |
| Cài đặt | Tên, logo, miền email cho phép, múi giờ, thông tin liên hệ |

### 4.4. Giao diện quản lý kỳ thi/Giáo viên

Đường dẫn chính tiếp tục dưới `/ui/exams` nhưng danh sách đã được lọc theo
assignment:

| Màn hình | Nội dung/chức năng |
|---|---|
| Kỳ thi của tôi | Thẻ/bảng kỳ thi được giao, trạng thái và hành động nhanh |
| Tạo kỳ thi | Wizard: thông tin → thời gian → xác thực → thiết bị → giám sát → rà soát |
| Tổng quan kỳ thi | Thời gian, mã tham gia, danh sách kiểm tra mức sẵn sàng và số thí sinh/phiên |
| Cấu hình | Chính sách đã kế thừa và phần được phép ghi đè |
| Nhân sự | Chủ kỳ thi, người quản lý, giám thị và ca trực; chỉ chọn thành viên sẵn có |
| Thí sinh | Danh sách, trạng thái tham gia, vấn đề xác thực/thiết bị |
| Giám sát trực tiếp | Điểm rủi ro từ hình ảnh và mức toàn vẹn trình duyệt được tách riêng, kèm bộ lọc cảnh báo |
| Sự cố cần duyệt | Hàng đợi dữ liệu giám sát, ghi chú, kết luận và lịch sử người xử lý |
| Báo cáo | Báo cáo kỳ thi/phiên, trạng thái sinh file, tải xuống |

Nút hành động cần phản ánh lifecycle. Ví dụ chỉ sửa cấu hình đầy đủ khi `draft`,
chỉ xoay code khi chưa `closed`, và không cho xóa cứng kỳ thi đã có phiên.

## 5. Mô hình dữ liệu mục tiêu

Không thay đổi schema telemetry/violation JSONL. Phần nâng cấp chỉ thay lớp SQL
quản trị và chỉ mục truy vấn.

### 5.1. Bảng chính

| Bảng | Trường quan trọng | Mục đích |
|---|---|---|
| `users` | `id, email, password_hash, status, session_version` | Danh tính đăng nhập; không gắn cứng một tổ chức trong mô hình đích |
| `organizations` | `id, name, slug, status, settings, quota, retention_days` | Tenant và chính sách tổ chức |
| `organization_memberships` | `user_id, org_id, role, status, invited_by, expires_at` | Gán `org_admin`/`exam_manager` theo tổ chức |
| `system_roles` | `user_id, role, status` | Gán `system_admin` qua quy trình riêng |
| `exam_assignments` | `exam_id, user_id, assignment_role, assigned_by, expires_at` | Owner/manager/proctor của từng kỳ thi |
| `invitations` | `org_id, email, role, token_hash, expires_at, accepted_at` | Mời người dùng bằng token một lần |
| `audit_logs` | actor, scope, action, resource, outcome, request metadata, change summary | Nhật ký bất biến phục vụ điều tra |
| `access_grants` | requester, org_id, reason, scope, approved_by, expires_at | Phiên truy cập ngoại lệ có thời hạn |

`Exam` cần thêm `owner_user_id`, lifecycle `draft/scheduled/open/closed/archived`,
`scheduled_start_at`, `scheduled_end_at`, `version` để optimistic locking và
`archived_at`. Không dùng xóa cứng cho kỳ thi đã sinh phiên.

### 5.2. Ràng buộc bắt buộc

- Unique `(user_id, org_id)` cho membership đang hoạt động.
- Unique `(exam_id, user_id)` cho assignment đang hoạt động.
- Mọi `exam_assignments.user_id` phải có membership active trong cùng tổ chức
  với kỳ thi.
- `system_admin` không được tạo qua endpoint quản lý thành viên tổ chức.
- Organization Admin không được tự xóa Organization Admin cuối cùng.
- Không cho đổi `Exam.org_id` sau khi đã tạo.
- Nhật ký hoạt động chỉ append; ứng dụng không có endpoint update/delete.
- Index tối thiểu trên `org_id`, `exam_id`, `user_id`, `status`, `created_at` và
  tổ hợp dùng trong danh sách dashboard.

## 6. Thiết kế authorization ở backend

### 6.1. Luồng quyết định quyền

Mỗi request quản trị đi qua các bước:

1. Xác thực token/cookie và trạng thái tài khoản.
2. Nạp membership hoặc system role hiện hành từ DB/cache có thời hạn ngắn.
3. Xác định tenant từ resource hoặc active context phía server.
4. Kiểm tra capability của vai trò.
5. Kiểm tra resource scope: cùng `org_id` và assignment hợp lệ.
6. Kiểm tra trạng thái tổ chức/kỳ thi, chính sách deny và điều kiện nghiệp vụ.
7. Thực hiện giao dịch và ghi nhật ký với cùng `request_id`.

Policy cốt lõi cho dữ liệu kỳ thi:

```text
allow(user, action, exam) khi:
  account_active
  AND organization_active
  AND (
    exam_manager_membership(user, exam.org_id)
      AND exam_assignment_allows(user, exam.id, action)
    OR valid_break_glass_grant(user, exam.org_id, action)
  )
```

Organization Admin không nằm ở nhánh dữ liệu kỳ thi, kể cả khi còn assignment
lịch sử. System Admin không nằm ở nhánh cho phép mặc định đối với evidence.

### 6.2. Capability đề xuất

Không rải chuỗi role trong router. Khai báo capability tập trung, ví dụ:

```text
system.organizations.manage
system.security.read
org.members.read
org.members.manage
org.policy.manage
org.audit.read
exam.create
exam.read
exam.manage
exam.assign
exam.monitor
exam.sessions.end
exam.evidence.read
exam.reports.export
```

Dependency/policy service nên trả về `AuthorizationContext` gồm `user_id`,
`active_org_id`, roles, capabilities và assignment. Router gọi policy trước khi
query hoặc mutation; service/repository vẫn bắt buộc nhận scope để tránh một
endpoint mới vô tình query toàn bảng.

### 6.3. Quy tắc API

- Tách namespace: `/system/...` cho System Admin; `/organizations/{org_id}/...`
  cho quản trị tổ chức; `/exams/{exam_id}/...` cho vận hành kỳ thi.
- Với Organization Admin/Exam Manager, không lấy `org_id` trong payload để quyết
  định quyền. Lấy tenant từ membership/resource đã xác thực.
- Query luôn bắt đầu bằng tenant filter, sau đó mới lọc ID tài nguyên.
- Trả `404` khi resource nằm ngoài scope để không làm lộ sự tồn tại; trả `403`
  khi resource thuộc scope nhưng thiếu capability.
- Mọi mutation nhạy cảm nhận `reason`, hỗ trợ idempotency key và dùng transaction.
- Danh sách phải phân trang, giới hạn sort/filter allowlist và không trả trường
  nhạy cảm nếu màn hình không cần.
- WebSocket dashboard áp dụng cùng policy lúc kết nối và kiểm tra lại khi role,
  assignment, trạng thái kỳ thi hoặc tổ chức thay đổi.

### 6.4. Token và thu hồi quyền

JWT chỉ dùng để xác thực danh tính, không nên tin role cũ trong token suốt thời
gian dài. Có hai lựa chọn:

- Access token ngắn hạn và resolve membership hiện hành ở mỗi request/cache.
- Hoặc thêm `session_version`/`permissions_version`, tăng version khi khóa user
  hay đổi quyền và từ chối token cũ.

Sau khi thu hồi role/assignment phải đóng WebSocket liên quan, hủy session web
và ghi nhật ký. Token `exam_session` của thí sinh vẫn tách loại hoàn toàn với token
người quản trị như hiện tại.

## 7. Nhật ký hoạt động, bảo mật và quyền riêng tư

Nhật ký hoạt động tối thiểu gồm: đăng nhập, đăng xuất, đăng nhập thất bại, mời/khóa user,
đổi role, đổi policy, tạo/mở/đóng kỳ thi, xoay join code, xem/tải evidence, kết
thúc phiên, xuất báo cáo, quyền truy cập ngoại lệ và yêu cầu xóa dữ liệu.

Mỗi bản ghi gồm:

- `actor_user_id`, vai trò và active organization tại thời điểm hành động.
- `action`, `resource_type`, `resource_id`, `org_id`, `exam_id` nếu có.
- `outcome`, mã lỗi, `request_id`, IP đã chuẩn hóa và user-agent.
- Tóm tắt before/after đã loại secret, password hash, token và dữ liệu sinh trắc.
- Timestamp server theo UTC.

Các kiểm soát bổ sung:

- MFA bắt buộc cho System Admin, khuyến nghị/bắt buộc theo chính sách cho
  Organization Admin.
- Xác thực lại khi đổi role, khóa tổ chức, xuất hàng loạt hoặc cấp quyền truy cập ngoại lệ.
- Least privilege cho tài khoản DB; backup/restore và retention theo tenant.
- Không dùng kết quả AI làm quyết định kỷ luật duy nhất; sự cố cần trạng thái
  `new/in_review/confirmed/dismissed` và lưu người kết luận.
- Export dùng job nền, link tải một lần có hạn, watermark/ghi nhật ký và không gửi file
  nhạy cảm trực tiếp qua email.

## 8. Lộ trình triển khai

### Giai đoạn 1 — khóa ranh giới hiện tại

- Đổi tên ngữ nghĩa `admin → org_admin`, `proctor → exam_manager` nhưng hỗ trợ
  mapping tương thích trong thời gian migration.
- Thêm `ExamAssignment`; backfill người tạo là `owner` và phân công các user cần
  truy cập kỳ thi hiện có.
- Sửa list/detail/WebSocket để Exam Manager chỉ thấy kỳ thi được giao.
- Thêm test ma trận quyền và test IDOR cho REST, file download và WebSocket.

### Giai đoạn 2 — quản trị tổ chức

- Thêm membership, invitation, trạng thái user và màn hình Người dùng/Chính sách.
- Thêm nhật ký hoạt động append-only và ghi nhật ký cho mọi mutation/truy cập evidence.
- Bổ sung lifecycle kỳ thi, review queue và optimistic locking.

### Giai đoạn 3 — System Admin

- Tách namespace `/system`, dashboard vận hành và quản lý tenant/quota.
- Thêm System Admin qua bootstrap CLI hoặc quy trình hai người; không có public
  registration cho vai trò này.
- Thêm MFA, quyền truy cập ngoại lệ, cảnh báo an ninh và thu hồi phiên tức thời.

### Giai đoạn 4 — tăng cường production

- PostgreSQL Row-Level Security như lớp phòng thủ bổ sung, Redis cho cache quyền,
  rate limit và fan-out nhiều worker.
- Job queue cho export/retention, object storage mã hóa và signed URL ngắn hạn.
- Kiểm thử permission snapshot, policy regression, tải đồng thời và quy trình
  backup/restore.

## 9. Tiêu chí nghiệm thu

- System Admin, Organization Admin và Exam Manager nhìn thấy đúng menu/phạm vi.
- Thay URL/ID không thể đọc kỳ thi, phiên, ảnh hoặc report ngoài scope.
- Exam Manager không được phân công không nhận được event WebSocket của kỳ thi.
- Thu hồi role/assignment có hiệu lực với REST và WebSocket đang mở.
- System Admin không xem được evidence nếu chưa có quyền truy cập ngoại lệ hợp lệ.
- Mọi thay đổi quyền và truy cập dữ liệu nhạy cảm đều có nhật ký hoạt động tra cứu được.
- Không thể tạo System Admin từ UI/API của Organization Admin.
- Tổ chức bị khóa không thể đăng nhập mới, mở kỳ thi hay nối dashboard.
- Các test isolation hiện có tiếp tục pass trong suốt migration.
