# Browser Exam Guard (Chrome/Firefox)

WebExtension này là client giám sát trình duyệt của hệ thống Giám Thị Số. Một
source được build thành hai gói Manifest V3:

- Chrome 116+ dùng extension service worker và WebSocket keepalive 15 giây.
- Firefox 140+ dùng background event page và built-in data-collection consent.

Camera/microphone/screen-share được bật qua popup overlay nằm trên trang thi,
có preview và chỉ báo rõ ràng. Background không quay ẩn và không truyền video
liên tục. Extension hiện giám sát tính toàn vẹn trình duyệt; pipeline CV Python
bảy tín hiệu vẫn là module riêng và chưa được port sang WebAssembly/WebGPU.

Nhấn biểu tượng extension trên thanh công cụ sẽ mở panel tham gia kỳ thi ngay
dưới biểu tượng. Các màn hình nội bộ không mở thành tab hoặc cửa sổ riêng.

## Build và test

Yêu cầu Node.js 20+:

```bash
cd extension
npm test
npm run build
```

Kết quả:

```text
dist/chrome/
dist/firefox/
```

Không có thư viện JavaScript hoặc CDN bên thứ ba trong runtime extension.

## Cài development

Chrome:

1. Mở `chrome://extensions`.
2. Bật **Developer mode**.
3. Chọn **Load unpacked** và trỏ tới `extension/dist/chrome`.
4. Nhấn biểu tượng extension để mở panel tham gia.

Firefox:

1. Mở `about:debugging#/runtime/this-firefox`.
2. Chọn **Load Temporary Add-on**.
3. Chọn `extension/dist/firefox/manifest.json`.

Firefox build khai báo built-in consent chính xác cho dữ liệu nhận dạng/xác
thực, browsing activity và website activity bắt buộc. `technicalAndInteraction`
là tùy chọn; nếu người dùng từ chối, extension không truyền browser version,
platform hoặc capability list. Android được vô hiệu hóa vì UI/monitor này chỉ
dành cho desktop.

Bản Firefox temporary mất sau khi khởi động lại. Triển khai thật cần ký add-on
qua AMO hoặc chính sách enterprise; Chrome triển khai thật nên dùng Chrome Web
Store hoặc force-install enterprise để extension ID ổn định.

## Hai chế độ xác thực

Giám thị chọn chính sách khi tạo kỳ thi. Thí sinh không tự đổi chế độ.

### `manual`

Extension yêu cầu đủ:

- Họ và tên.
- Mã thí sinh.

Backend chuẩn hóa dữ liệu, lưu phương thức xác thực và từ chối dùng lại cùng mã
thí sinh trong một kỳ thi.

### `google`

Lần đầu:

1. Extension mở `identity.launchWebAuthFlow()` do thao tác trực tiếp của người
   dùng.
2. Backend dùng Authorization Code + PKCE, kiểm tra `state`, `nonce`, chữ ký ID
   token, audience và `email_verified`.
3. Backend chỉ lưu claim OIDC tối thiểu (`sub`, tên, email, ảnh đại diện và
   Workspace domain nếu có).
4. Google access token/refresh token không được lưu.
5. Extension nhận một opaque candidate-device token riêng, có hạn dùng và có
   thể thu hồi.

Lần sau, extension dùng token thiết bị để lấy lại hồ sơ đã xác minh. Token nằm
trong `storage.local` vì cần tồn tại qua lần mở trình duyệt sau; vùng lưu này
không được mã hóa bởi WebExtension API. Source giới hạn nó cho trusted extension
contexts bằng `setAccessLevel`, bind với `device_id`, đặt TTL và cung cấp nút
thu hồi. Không nên coi đây là hardware-backed credential.

## Cấu hình Google OAuth

Tạo OAuth Client loại **Web application** trong Google Cloud Console. Authorized
redirect URI của Google là callback HTTPS của backend, ví dụ:

```text
https://proctor.example.edu/candidate-auth/google/callback
```

Sau khi cài extension, trang setup hiển thị chính xác OAuth redirect của
extension. Thêm URI đó vào allowlist backend, không thêm làm callback Google.

```dotenv
GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_CALLBACK_URL=https://proctor.example.edu/candidate-auth/google/callback
OAUTH_EXTENSION_REDIRECT_URIS=https://<chrome-id>.chromiumapp.org/google,https://<firefox-id>.extensions.allizom.org/google
CANDIDATE_TOKEN_TTL_DAYS=90
```

Nếu giới hạn tài khoản trường/công ty, nhập `google_allowed_domain` khi tạo kỳ
thi. Backend kiểm tra claim `hd` đã ký, không chỉ so chuỗi phía sau email.

## Luồng phiên thi

1. Mở panel từ biểu tượng extension và nhập mã tham gia. Backend được cấu hình
   nội bộ, không hiển thị trên panel.
2. Extension xin host permission cho đúng backend và origin bài thi.
3. Backend trả về chính sách xác thực/thiết bị.
4. Thí sinh xác thực và đồng ý chính sách.
5. Extension kiểm tra camera/microphone trước khi tạo phiên.
6. Backend tạo session và cấp session JWT.
7. Extension đổi JWT qua REST lấy WebSocket ticket 30 giây dùng một lần.
8. Ticket đi trong `Sec-WebSocket-Protocol`; session JWT không nằm trong URL.
9. Popup overlay trên trang thi xin quyền thiết bị; sau khi sẵn sàng mới thu nhỏ.
10. Background gửi heartbeat, xếp hàng sự kiện và chờ ACK trước khi xóa.

## Dữ liệu được ghi nhận

- Chuyển tab, mở tab mới và rời cửa sổ.
- Ẩn/hiện tab bài thi và thời lượng vắng do server đo.
- Thoát/vào fullscreen.
- Hành động copy, cut, paste và menu chuột phải; không đọc nội dung clipboard.
- Điều hướng khỏi origin bài thi.
- Camera/microphone/screen-share bị mute, dừng hoặc thiếu quyền.
- Heartbeat và phiên bản extension/browser.

Server tự gắn timestamp, tự tính mức độ và điểm integrity riêng. Dữ liệu này
không được cộng lẫn với risk score CV và không nên tự động dùng để kết luận gian
lận.

## Giới hạn thực tế

- Extension không thể khóa ứng dụng ngoài trình duyệt, máy ảo, điện thoại thứ
  hai hoặc extension khác một cách tuyệt đối.
- Thí sinh có quyền quản trị máy vẫn có thể gỡ/sửa extension unpacked. Kỳ thi
  rủi ro cao cần extension đã ký và force-install/managed browser.
- Camera ảo, replay và deepfake cần liveness/anti-spoof chuyên dụng hoặc native
  companion; Google login chỉ xác minh quyền sở hữu tài khoản.
- Firefox temporary add-on chỉ dùng để test.
- Background có thể bị browser dừng; `storage.session`, WebSocket keepalive và
  alarm giúp phục hồi nhưng không thay thế device attestation.

Tài liệu nền tảng chính thức:

- [Chrome: WebSocket trong extension service worker](https://developer.chrome.com/docs/extensions/how-to/web-platform/websockets)
- [Chrome: service worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
- [MDN: background MV3 đa trình duyệt](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background)
- [Chrome Identity API](https://developer.chrome.com/docs/extensions/reference/api/identity)
- [Google OAuth web-server flow](https://developers.google.com/identity/protocols/oauth2/web-server)
