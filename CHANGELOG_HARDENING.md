# Extension/OIDC upgrade (2026-08)

- Thêm WebExtension Manifest V3 dùng chung source cho Chrome 116+ và Firefox
  140+, gồm setup, monitor có preview, background heartbeat/reconnect, queue
  sự kiện có ACK và dynamic origin permissions.
- Thêm chính sách kỳ thi `manual` hoặc `google`, URL bài thi, extension version
  tối thiểu, fullscreen/camera/microphone/screen-share/clipboard/focus timeout.
- Thêm Google OIDC Authorization Code + PKCE/state/nonce, exact redirect
  allowlist, ID-token verification và Workspace `hd` restriction. Không lưu
  Google access/refresh token.
- Thêm opaque candidate-device token có TTL, hash-only storage, device binding
  và revoke; hồ sơ đã xác minh được dùng lại ở lần thi sau.
- Thêm WebSocket ticket dùng một lần qua `Sec-WebSocket-Protocol` cho browser
  API không hỗ trợ custom Authorization header.
- Thêm `browser_events.jsonl`, server-side severity/integrity score, dashboard
  và báo cáo riêng; không trộn với CV risk score.
- Firefox manifest khai báo built-in data consent hiện hành; technical data là
  tùy chọn và bị lược bỏ khi người dùng không đồng ý.

Kết quả chốt của bản nâng cấp: `254 passed` cho Python, `4 passed` cho Node và
Firefox `web-ext lint` đạt `0 errors / 0 warnings`.

# Hardening changes trước đó

Tệp này tóm tắt các thay đổi khắc phục sau đợt review source.

- Loại stored XSS ở dashboard; bỏ JWT khỏi `localStorage` và URL WebSocket.
- Thêm cookie HttpOnly, CSP/security headers, host/HTTPS controls và logout.
- Thêm strict WebSocket schema, server timestamps, risk/state/violation
  cross-check, heartbeat, message/rate/idle limits và disconnect state.
- Thêm upload snapshot thật với type/size/hash/containment validation; chặn đọc
  file tùy ý khi tạo báo cáo.
- Gom telemetry theo chu kỳ, ghi `signals.jsonl` phía server và phát dashboard
  theo snapshot trạng thái đã xác minh.
- Thêm exam open/closed, join-code expiry/rotation và rate limit endpoint công
  khai.
- Bỏ production default secrets, tách dependency backend nhẹ, chặn cấu hình
  nhiều worker chưa có pub/sub.
- Thêm blink liveness cơ bản, cleanup khi enrollment/camera lỗi, hỗ trợ đúng
  `report.formats`, đổi nhãn mắt nhắm thành `EYES_CLOSED`.
- Hạ threshold nguồn MTCNN để threshold riêng của MultiFace có tác dụng; lazy
  load model và thêm script prefetch.
- Mở rộng test cho auth cookie/XSS, rate limit, org isolation, exam lifecycle,
  telemetry tampering, snapshot upload/path traversal, disconnect và liveness.

Kết quả bản trước: `250 passed` với dependency khai báo trong `requirements.txt`.
