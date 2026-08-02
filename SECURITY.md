# Security model

## Phạm vi tin cậy

Backend, database và reverse proxy phải chạy trong hạ tầng do đơn vị tổ chức
kiểm soát. Trình duyệt giám thị được xem là trusted sau đăng nhập. Máy thí sinh
không được xem là trusted tuyệt đối.

Server thực hiện các kiểm tra có thể xác minh từ protocol:

- Tách token `user` và `exam_session`; kiểm tra quyền và `org_id` tại mọi API.
- Dashboard dùng cookie `HttpOnly`, `SameSite=Strict`; token không nằm trong URL,
  `localStorage` hoặc WebSocket query string.
- Schema WebSocket cấm field lạ, giới hạn kiểu/độ dài/kích thước/tốc độ.
- Telemetry phải chứa đúng bảy signal. Risk score, session hysteresis, severity,
  primary violation và contributions được server tính/đối chiếu lại.
- Timestamp chính do server sinh; `video_time_sec` bị chặn theo thời lượng phiên
  và phải tăng đơn điệu.
- Heartbeat/idle timeout làm lộ phiên dừng hoặc mất kết nối.
- Snapshot chỉ nhận JPEG/PNG tối đa 2 MiB, kiểm tra magic bytes + SHA-256, dùng
  tên server sinh và atomic replace. Báo cáo chỉ đọc file thường nằm trong
  `<session>/snapshots`, không theo symlink và không đọc path tùy ý từ client.
- Dashboard không dựng HTML từ dữ liệu người dùng và được bảo vệ bằng CSP,
  `nosniff`, frame denial, referrer/permissions policy.
- Login/register/join và WebSocket có rate limit trong process.
- Join code hết hạn, có trạng thái open/closed và có thể rotate.
- Google OIDC dùng Authorization Code + PKCE, `state`, `nonce`, callback exact
  match và ID-token verification. Backend không lưu access/refresh token của
  Google. Claim `sub`, `email_verified` và `hd` (nếu giới hạn Workspace) mới là
  dữ liệu quyết định; tên/email do extension gửi không được tin.
- Candidate-device token là opaque random secret; database chỉ lưu SHA-256,
  token có TTL, bind với device ID và có thể thu hồi. Token này không phải token
  Google.
- Browser WebSocket lấy ticket ngẫu nhiên 30 giây qua REST đã xác thực. Ticket
  dùng một lần trong `Sec-WebSocket-Protocol`; JWT phiên không nằm trong URL.
- Browser event có allowlist/schema, sequence/event-id, server timestamp và
  server-side severity. Integrity score không được cộng lẫn với risk CV.

## Giới hạn không thể che giấu

Một client Python chạy trên máy do thí sinh sở hữu có thể bị patch. Kẻ tấn công
có thể giả cả bảy signal và risk theo một chuỗi toán học hợp lệ, thay camera hoặc
can thiệp trước khi telemetry được tạo. Server-side validation làm giả mạo đơn
giản khó hơn và tạo audit trail tốt hơn, nhưng không phải remote attestation.

Điều tương tự áp dụng cho extension unpacked hoặc máy mà thí sinh có quyền quản
trị: họ có thể gỡ, sửa hoặc giả message. Heartbeat làm hành vi tắt extension dễ
quan sát hơn nhưng không chứng minh mã nguyên bản đang chạy. Production cần bản
đã ký, extension ID cố định và force-install bằng Chrome/Firefox enterprise
policy. Extension không thể quan sát đáng tin cậy ứng dụng ngoài trình duyệt,
điện thoại thứ hai, máy ảo hoặc màn hình ngoài.

`storage.local` của WebExtension không được mã hóa. Source giới hạn candidate
token cho trusted extension contexts, đặt TTL và cung cấp thu hồi, nhưng malware
có quyền đọc profile trình duyệt vẫn có thể đánh cắp cả token và device ID. Kỳ
thi rủi ro cao nên yêu cầu Google re-auth gần thời điểm thi hoặc dùng credential
hardware-backed/device attestation.

Thử thách chớp mắt hiện tại chặn ảnh tĩnh đơn giản. Nó không được thiết kế để
chống video replay chất lượng cao, camera ảo hay deepfake. Không dùng kết quả CV
làm căn cứ kỷ luật duy nhất; cần quy trình người giám thị xem lại bằng chứng.

Ứng dụng cũng không tự phát hiện camera bị che trước khi client khởi động, không
đồng bộ bù log khi offline, và không bundle model weights. Chạy
`scripts/prefetch_models.py` trước một phiên cần offline.

## Checklist production

- Tạo `JWT_SECRET_KEY` ngẫu nhiên tối thiểu 32 ký tự và mật khẩu DB riêng; không
  commit file `.env`.
- Bắt buộc HTTPS/WSS ở reverse proxy, bật `COOKIE_SECURE=true` và
  `FORCE_HTTPS=true`, đặt `ALLOWED_HOSTS` chính xác.
- Đăng ký chính xác `GOOGLE_OAUTH_CALLBACK_URL` trong Google Cloud Console và
  exact allowlist mọi `OAUTH_EXTENSION_REDIRECT_URIS`; không dùng wildcard.
  Rotate client secret nếu bị lộ và không commit secret vào manifest/source.
- Chỉ yêu cầu scope Google `openid email profile`. Định kỳ thu hồi candidate
  devices cũ và đặt `CANDIDATE_TOKEN_TTL_DAYS` phù hợp chính sách.
- Chỉ chạy một backend worker. Trước khi scale ngang, thay connection manager và
  rate limiter in-memory bằng Redis/pub-sub + distributed rate limiting.
- Giới hạn truy cập PostgreSQL, volume `sessions`, backup và retention; ảnh khuôn
  mặt/vi phạm là dữ liệu nhạy cảm.
- Theo dõi dung lượng vì snapshot và report được lưu bền vững; đặt quota và lịch
  xóa phù hợp quy định địa phương.
- Đặt reverse-proxy body/message/connection limits và log cảnh báo disconnect,
  validation failure, login/join throttling.
- Ký/phân phối client và extension qua kênh quản lý; với kỳ thi rủi ro cao cần kiosk/lockdown,
  secure boot/device attestation và anti-spoofing chuyên dụng.
- Kiểm thử webcam, ánh sáng, false-positive và accessibility trên chính phần cứng
  triển khai. Các threshold mặc định chỉ là cấu hình khởi tạo.

## Secret và dữ liệu log

Không gửi `.env`, JWT, session token hoặc database URL vào issue/log công khai.
Server không cần và không chấp nhận path snapshot cục bộ để đọc file. Khi chia sẻ
log để debug, hãy xóa tên thí sinh, ảnh, token, join code và định danh phiên.
