# Chương 6. Kiểm thử và đánh giá

## 6.1. Mục tiêu và phạm vi đánh giá

Chương này đánh giá hai loại thuộc tính khác nhau:

1. **Độ đúng của phần mềm:** mô-đun có thực hiện đúng hợp đồng, quyền truy cập và luồng nghiệp vụ hay không.
2. **Hiệu quả phát hiện bằng thị giác máy tính:** hệ thống nhận biết khung hình vi phạm trên bộ video có nhãn tham chiếu tốt đến mức nào.

Hai loại bằng chứng không thay thế cho nhau. Một ca kiểm thử đạt chỉ chứng minh phần cài đặt đáp ứng tình huống đã mô tả; kết quả đó không chứng minh mô hình có độ chính xác cao trong mọi điều kiện thực tế. Ngược lại, độ chính xác (Precision) hoặc độ bao phủ (Recall) cao trên một bộ dữ liệu không chứng minh hệ thống an toàn trước truy cập chéo tổ chức hoặc mã xác thực giả mạo.

Mã nguồn và bộ kiểm thử phần mềm có thể được chạy lại từ kho mã nguồn hiện tại. Ngược lại, bộ 25 video, nhãn tham chiếu, điểm kiểm tra mô hình và đầu ra đánh giá được tạo ở một môi trường khác, không có trong bản bàn giao. Vì vậy, các số liệu thị giác máy tính dưới đây được trình bày như kết quả đã được ghi nhận từ môi trường thực nghiệm, không phải kết quả được tái lập trong lần rà soát này. Những chỉ số có thể suy ra từ ma trận nhầm lẫn được tính lại để kiểm tra tính nhất quán số học.

## 6.2. Kiểm thử phần mềm trong kho mã nguồn

### 6.2.1. Phương pháp

Bộ kiểm thử Python được chạy bằng:

```bash
.venv\Scripts\python.exe -m pytest -q backend\tests tests
```

Bộ kiểm thử tiện ích mở rộng được chạy bằng:

```bash
cd extension
npm test
```

Kết quả ghi nhận ngày 12/08/2026 trên môi trường phát triển Windows hiện tại:

| Lần chạy | Kết quả | Thời gian |
|---|---:|---:|
| Toàn bộ Python, lần 1 | 308 đạt, 1 lỗi | 140,16 giây |
| Chạy riêng ca lỗi của lần 1 | 1 đạt | 1,50 giây |
| Toàn bộ Python, lần 2 | 309 đạt, 0 lỗi | 127,14 giây |
| Tiện ích mở rộng trên Node | 8 đạt, 0 lỗi | 138,00 ms theo Node test runner |

Ở lần chạy Python đầu tiên, ca `test_organization_audit_is_paged_and_resolves_actor_identity` thất bại vì thứ tự tài nguyên nhận được không đúng kỳ vọng (`resource-04` đứng trước `resource-00`). Ca này đạt khi chạy riêng và toàn bộ bộ kiểm thử cũng đạt ở lần chạy thứ hai. Kết quả cho thấy lỗi không tái hiện ổn định, nhưng vẫn cần được theo dõi như một nguy cơ phụ thuộc thứ tự hoặc không ổn định của kiểm thử; không nên chỉ công bố lần chạy thành công.

Mỗi lần chạy toàn bộ bằng Pytest ghi nhận 344 cảnh báo, chủ yếu liên quan đến thành phần sắp ngừng hỗ trợ trong Starlette/httpx, bộ chuyển đổi ngày giờ của SQLite và protobuf. Các cảnh báo không làm kiểm thử thất bại nhưng cần được xử lý hoặc theo dõi khi nâng phiên bản thư viện phụ thuộc.

### 6.2.2. Kiểm thử chuỗi xử lý thị giác máy tính và thuật toán

Các nhóm kiểm thử chính gồm:

- Công thức EAR, tỉ lệ miệng và chuyển đổi tọa độ.
- Cơ chế chống dao động theo thời lượng cho vắng mặt, mắt, vật thể và góc quay đầu.
- Lọc độ tin cậy của tín hiệu nhiều khuôn mặt.
- PnP trên góc quay tổng hợp biết trước.
- Độ tương đồng cosin, đăng ký khuôn mặt và chu kỳ xác minh danh tính.
- Kiểm tra sự hiện diện sống theo chuỗi mở–nhắm–mở.
- Tính chịu lỗi khi bộ phát hiện phát sinh ngoại lệ.
- Hợp đồng đủ bảy tín hiệu và bộ khởi tạo đọc đúng YAML.
- Máy trạng thái, cửa sổ trượt, vùng trễ, cạnh chuyển vào cảnh báo và nhiều tín hiệu đóng góp.
- Kiểm thử khởi tạo mô hình thật và kiểm thử tích hợp trên video mẫu.

Một số ca kiểm thử hồi quy xuất phát từ lỗi quan sát được trên webcam thật. Ví dụ, tín hiệu trạng thái mắt từng báo nhầm khi một mắt bị nén phối cảnh; kiểm thử hiện yêu cầu biến dạng của một mắt không được coi là nhắm, trong khi hai mắt cùng có EAR thấp vẫn phải kích hoạt điều kiện.

### 6.2.3. Kiểm thử dịch vụ phía máy chủ và bảo mật

Bộ kiểm thử phía máy chủ sử dụng FastAPI TestClient và cơ sở dữ liệu SQLite tạm thời cho từng ca. Các nhóm được kiểm tra gồm:

- Đăng ký, đăng nhập, cookie, đăng xuất và giới hạn tần suất.
- MFA của quản trị viên hệ thống, giới hạn số lần thử và khôi phục/đăng ký lại.
- Phân biệt mã xác thực người dùng, mã xác thực phiên, vé WebSocket và mã xác thực không hợp lệ.
- Tư cách thành viên ở nhiều tổ chức và chuyển tổ chức đang hoạt động.
- Quyền chức năng theo từng phân công kỳ thi; người quản lý ở kỳ thi A không có quyền quản lý ở kỳ thi B.
- Cô lập tổ chức trên danh sách phiên, kết thúc phiên, báo cáo, ảnh chụp và WebSocket của bảng điều khiển.
- Kế thừa chính sách và từ chối cấu hình làm yếu mức sàn hệ thống/tổ chức.
- Vòng đời, kiểm soát đồng thời lạc quan, mã tham gia và hạn mức phiên đồng thời.
- Google OIDC giả lập, `state`/PKCE/`nonce`/mã cấp quyền và mã xác thực thiết bị.
- Kiểm tra đủ bảy tín hiệu, tính lại mức rủi ro/toàn vẹn phía máy chủ và sự kiện trình duyệt.
- Tải ảnh chụp lên, chống tấn công duyệt đường dẫn, hậu kiểm sự cố và tác vụ báo cáo nền.
- Tiêu đề bảo mật, DOM an toàn và các đường dẫn giao diện.

Việc toàn bộ 309 ca đạt ở lần chạy thứ hai cho thấy mã nguồn có thể đáp ứng các hợp đồng và quy tắc đã được kiểm thử. Tuy nhiên, kết quả không ổn định của lần chạy đầu cho thấy độ tin cậy của bộ kiểm thử cũng cần được xem xét, đặc biệt đối với dữ liệu có cùng dấu thời gian hoặc thứ tự sắp xếp. Bộ kiểm thử không thay thế kiểm thử xâm nhập độc lập và không bao phủ hành vi của mọi trình duyệt hoặc thiết bị thực.

### 6.2.4. Kiểm thử tiện ích mở rộng

Tám ca kiểm thử Node kiểm tra giao diện thiết lập, luồng nhập mã, chuẩn hóa địa chỉ máy chủ, yêu cầu HTTPS ngoài `localhost`, so sánh phiên bản ngữ nghĩa, phân tích định danh trình duyệt, lọc dữ liệu chuyển hướng OAuth và cấu trúc gói tiện ích. Ngoài kiểm thử tự động, các API camera, chia sẻ màn hình, toàn màn hình và hành vi trình duyệt vẫn cần được kiểm tra thủ công trên Chrome và Firefox thực tế vì Node không mô phỏng đầy đủ hộp thoại cấp quyền và vòng đời tiến trình dịch vụ.

## 6.3. Đánh giá hoạt động của hệ thống đã triển khai

### 6.3.1. Phương pháp và tiêu chí đánh giá

Đánh giá hoạt động xem xét khả năng duy trì chuỗi nghiệp vụ từ cấu hình kỳ thi đến hậu kiểm. Bằng chứng sử dụng gồm mã nguồn, kiểm thử tự động, cấu trúc giao diện đã cài đặt, hợp đồng dữ liệu và trạng thái bền vững trong cơ sở dữ liệu hoặc kho bằng chứng. Việc một tuyến xử lý tồn tại không đồng nghĩa hệ thống đã sẵn sàng triển khai thực tế. Một luồng chỉ được kết luận đạt trong phạm vi kiểm thử khi đã có ca kiểm tra hành vi và điều kiện lỗi tương ứng; các tương tác phụ thuộc trình duyệt, webcam và hộp thoại cấp quyền được ghi rõ là cần xác nhận bổ sung.

Các tiêu chí gồm:

- **Tính đầy đủ nghiệp vụ:** có đủ bước chuẩn bị, tham gia, giám sát, kết thúc, hậu kiểm và tạo báo cáo.
- **Tính nhất quán dữ liệu:** trạng thái trên giao diện có nguồn từ dữ liệu máy chủ đã kiểm chứng; bằng chứng gắn đúng tổ chức, kỳ thi và phiên.
- **Khả năng quan sát:** người dùng nhận biết được trạng thái tải, lỗi, mất kết nối, kiểm tra trước phiên chưa đạt và tác vụ báo cáo thất bại.
- **An toàn phạm vi:** chức năng chỉ xuất hiện và chỉ được thực thi với vai trò hoặc năng lực hợp lệ.
- **Khả năng suy giảm có kiểm soát:** lỗi của một kênh không làm dữ liệu cũ bị trình bày như dữ liệu thời gian thực hoặc tạo trạng thái báo cáo thành công giả.

### 6.3.2. Đánh giá các kịch bản đầu-cuối

| Kịch bản | Luồng được kiểm chứng | Bằng chứng hiện có | Đánh giá |
|---|---|---|---|
| Chuẩn bị tổ chức | Tạo tổ chức, tư cách thành viên, vai trò, chính sách và hạn mức | Đường dẫn API/UI, chuyển đổi lược đồ và kiểm thử xác thực/RBAC/chính sách | Đạt trong phạm vi kiểm thử tự động |
| Chuẩn bị kỳ thi | Tạo kỳ thi, cấu hình, phân công, điều kiện sẵn sàng và mã tham gia | Kiểm thử vòng đời, kiểm soát đồng thời lạc quan, phân công và mã tham gia | Đạt trong phạm vi kiểm thử tự động |
| Thí sinh tham gia | Kiểm tra mã, xác thực thủ công/Google, ghi nhận sự đồng ý, cấp mã xác thực phiên | Xác thực thí sinh, Google OIDC giả lập, kiểm thử loại mã xác thực và thiết lập tiện ích | Đạt về logic; cần kiểm tra OAuth/quyền thực tế |
| Khởi động ứng dụng thị giác máy tính | IDLE → ENROLLMENT → xác minh sự hiện diện sống → MONITORING | Bộ điều khiển, đăng ký/xác minh sự hiện diện sống, kiểm thử khởi động cơ bản và tích hợp video | Đạt về chức năng; phụ thuộc webcam/môi trường |
| Giám sát trình duyệt | Kiểm tra trước phiên, thẻ/trạng thái tập trung/toàn màn hình/bảng tạm, nhịp kết nối | Mã nguồn tiện ích, kiểm thử Node và kiểm tra dữ liệu sự kiện trình duyệt | Đạt phần logic; cần chạy Chrome/Firefox thật |
| Truyền dữ liệu theo thời gian thực | Thông điệp mở đầu máy khách, dữ liệu giám sát, vi phạm, sự kiện trình duyệt, nhịp kết nối, phân phối tới bảng điều khiển | Lược đồ WebSocket, vé kết nối, số thứ tự/loại bỏ bản ghi trùng và kiểm thử quyền | Đạt trong phạm vi kiểm thử máy chủ |
| Giám sát và mở chi tiết phiên | Trạng thái ban đầu qua REST, cập nhật WebSocket, bộ lọc, dòng thời gian rủi ro/bằng chứng | Đường dẫn bảng điều khiển/mã nguồn tĩnh, cô lập tổ chức và kiểm thử WebSocket | Đạt về tích hợp phía máy chủ; cần kiểm tra giao diện đa phiên thực tế |
| Kết thúc và hậu kiểm | Kết thúc phiên, hậu kiểm sự cố, truy cập ảnh chụp và kiểm toán | Kiểm thử kết thúc phiên, hậu kiểm, ảnh chụp/tấn công duyệt đường dẫn và kiểm toán | Đạt trong phạm vi kiểm thử tự động |
| Sinh báo cáo | Tác vụ báo cáo → tiến trình nền → HTML/PDF → trạng thái hoàn thành/thất bại | Kiểm thử tính nhất quán của báo cáo, tác vụ báo cáo và trình đọc dung nạp lỗi | Đạt về chức năng |
| Mất kết nối/lỗi dữ liệu | WebSocket gián đoạn, thông điệp sai lược đồ, dữ liệu trùng, máy chủ không khả dụng | Kiểm tra dữ liệu, loại bỏ bản ghi trùng, bộ quản lý kết nối và hành vi cục bộ theo khả năng tốt nhất | Đạt một phần; cần thử nghiệm mạng gián đoạn dài |

Kết quả cho thấy các phân hệ được nối với nhau bằng hợp đồng dữ liệu: chính sách từ máy chủ điều khiển bước kiểm tra trước phiên; mã xác thực phiên xác định đúng phiên thi; dữ liệu giám sát đã kiểm chứng cập nhật trạng thái hiện tại và kho bằng chứng; bảng điều khiển, hậu kiểm và báo cáo cùng sử dụng mã phiên làm khóa truy vết. Những nội dung còn thiếu bằng chứng chủ yếu thuộc môi trường thực tế: vòng đời tiến trình dịch vụ, hộp thoại cấp quyền, tải đồng thời nhiều phiên và các dạng mất mạng kéo dài.

### 6.3.3. Đánh giá luồng dữ liệu và tính nhất quán

Luồng dữ liệu tại Hình 4.9 được đánh giá theo ba chặng. Ở chặng thu thập, ứng dụng thị giác máy tính tạo đủ bảy tín hiệu và tiện ích mở rộng chỉ gửi các sự kiện trình duyệt đã định nghĩa; dữ liệu ảnh không được truyền liên tục. Ở chặng kiểm chứng, máy chủ từ chối trường thừa, miền giá trị sai, dấu thời gian thiếu múi giờ, số thứ tự trùng và đường dẫn ảnh chụp do máy khách tự quyết định. Ở chặng khai thác, dữ liệu thời gian thực chỉ được phát đến bảng điều khiển sau khi xác thực quyền và kiểm tra hợp lệ; SQL và kho bằng chứng lưu hai biểu diễn phục vụ hai kiểu truy cập khác nhau.

Các bất biến quan trọng đã được kiểm thử gồm:

- Một bản cập nhật giám sát phải chứa đúng bảy tín hiệu với bảy trạng thái không trùng.
- Điểm rủi ro, mức nghiêm trọng, tín hiệu chính/đóng góp và mức toàn vẹn trình duyệt không được tin trực tiếp nếu có thể tính lại phía máy chủ.
- `ExamSession` giữ bản sao trạng thái mới nhất để bảng điều khiển nạp nhanh; JSONL giữ chuỗi sự kiện để dựng dòng thời gian và báo cáo.
- Ảnh chụp phải đúng định dạng, kích thước và hàm băm, đồng thời nằm trong thư mục phiên do máy chủ quản lý.
- Bản hậu kiểm sự cố bổ sung kết luận của con người mà không sửa sự kiện vi phạm nguyên bản.
- WebSocket của bảng điều khiển dùng vé kết nối ngắn hạn, một lần; quyền vẫn được kiểm tra theo phân công kỳ thi.

Nhờ các bất biến này, cùng một sự kiện có thể được truy từ thẻ trên bảng điều khiển đến trang chi tiết phiên, dòng JSONL, ảnh chụp và báo cáo. Giới hạn hiện tại là việc đồng bộ ứng dụng thị giác máy tính và tiện ích mở rộng vào cùng một phiên vẫn phụ thuộc cách triển khai phía máy khách; hệ thống chưa có cầu nối nhắn tin với ứng dụng cục bộ (native messaging) hoàn chỉnh để ràng buộc hai tiến trình trên máy thí sinh ở mức chống giả mạo.

### 6.3.4. Đánh giá giao diện và khả năng vận hành

Giao diện đã bao phủ các nhiệm vụ chính được mô tả tại mục 5.8. Khung web tách không gian làm việc của hệ thống, tổ chức và kỳ thi; tiện ích trình bày luồng tham gia theo từng bước; ứng dụng máy tính để bàn phản ánh máy trạng thái; trang chi tiết phiên và báo cáo phục vụ hậu kiểm. Cách chia này phù hợp với tần suất sử dụng: quản trị viên không cần thấy dữ liệu ở cấp khung hình, thí sinh không cần thấy bảng điều khiển nhiều phiên, còn giám thị cần ưu tiên rủi ro, mức toàn vẹn, cảnh báo và bằng chứng.

Về phản hồi trạng thái, bảng điều khiển có chỉ báo WebSocket, tiện ích có vùng kiểm tra trước phiên/trạng thái, tác vụ báo cáo có các trạng thái `pending/processing/failed/completed`, và ứng dụng máy tính để bàn có các trạng thái `IDLE/ENROLLMENT/MONITORING/GENERATING_REPORT/ENDED`. Đây là nền tảng để người dùng nhận biết tiến trình thay vì thực hiện lại thao tác do không biết hệ thống đã nhận lệnh hay chưa.

Tuy nhiên, đánh giá giao diện trong kho mã nguồn chủ yếu dựa trên tuyến xử lý, hợp đồng DOM, JavaScript và kiểm thử phía máy chủ/Node. Cần bổ sung một vòng nghiệm thu có người dùng và ảnh chụp thật cho các giao diện được mô tả tại mục 5.8. Phạm vi kiểm tra tối thiểu gồm màn hình 1366×768; bảng có dữ liệu dài; trạng thái rỗng và lỗi; điều hướng bằng bàn phím; trường hợp từ chối cấp quyền; kết nối lại WebSocket; và khả năng hiển thị tiếng Việt trong PDF.

### 6.3.5. Tổng hợp mức độ hoạt động

| Phân hệ | Kết quả chính | Hạn chế cần công bố |
|---|---|---|
| Ứng dụng thị giác máy tính | Đủ vòng đời, bảy tín hiệu, phép tổng hợp, nhật ký và báo cáo cục bộ | FPS và độ ổn định phụ thuộc thiết bị/camera |
| Tiện ích mở rộng trình duyệt | Có thiết lập, chính sách, sự đồng ý, kiểm tra trước phiên và sự kiện trình duyệt | Node không mô phỏng đầy đủ quyền trình duyệt/tiến trình dịch vụ |
| Nền tảng máy chủ | Đủ xác thực, tổ chức/RBAC, kỳ thi/phiên, bằng chứng, hậu kiểm, báo cáo | Chưa thay thế kiểm thử xâm nhập và kiểm thử tải ở môi trường chính thức |
| Bảng điều khiển thời gian thực | Có trạng thái ban đầu, vé WebSocket và phân phối cập nhật | Cần thử nghiệm nhiều giám thị/nhiều tiến trình trên hạ tầng thật |
| Lưu trữ và báo cáo | Trạng thái hiện tại trong SQL kết hợp JSONL/ảnh chụp, báo cáo chạy nền | Cần đo dung lượng, thời hạn lưu giữ và khôi phục dữ liệu dài hạn |
| Khả năng truy vết | Có mã yêu cầu/nhật ký kiểm toán, mã phiên, mã sự kiện, kết quả hậu kiểm và tác vụ báo cáo | Cần chuẩn hóa khả năng quan sát tập trung khi triển khai phân tán |

Tổng thể, hệ thống đạt mức **nguyên mẫu tích hợp có thể trình diễn và kiểm thử đầu-cuối**. Hệ thống đã có quản trị, phân quyền, cập nhật thời gian thực, quản lý bằng chứng và báo cáo, nhưng chưa đạt mức sẵn sàng triển khai diện rộng. Để nâng mức trưởng thành, cần bổ sung kiểm thử trên trình duyệt và thiết bị thật, kiểm thử tải nhiều phiên, kiểm thử bảo mật độc lập, giám sát vận hành và quy trình sao lưu/khôi phục.

### 6.3.6. Kịch bản nghiệm thu thủ công khi chạy hệ thống

Bảng sau là mẫu biên bản cần hoàn thiện trong lần chạy nghiệm thu. Cột “Kết quả thực tế” được chủ động để ở trạng thái chưa ghi nhận; chỉ chuyển sang “Đạt/Không đạt” sau khi thực hiện đúng bước, lưu ảnh chụp hoặc nhật ký và ghi rõ môi trường. Cách trình bày này tránh biến sự tồn tại của tuyến xử lý hoặc kết quả kiểm thử tự động thành bằng chứng giả định về trải nghiệm trên thiết bị thật.

| Mã | Chuẩn bị và thao tác | Kết quả mong đợi | Bằng chứng cần lưu | Kết quả thực tế |
|---|---|---|---|---|
| `MT-01` | Đăng ký tài khoản/tổ chức; đăng nhập và hoàn tất MFA | Tạo đúng người dùng/tư cách thành viên; cookie phiên hợp lệ; MFA sai bị từ chối | Ảnh màn hình đăng ký, đăng nhập, tài khoản và nhật ký xác thực/kiểm toán | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-02` | Quản trị viên hệ thống/tổ chức mở chính sách, bảo mật, nhật ký và thử truy cập ngoài quyền | Trình đơn đúng vai trò; thao tác hợp lệ thành công; truy cập chéo bị `403/404` | Ảnh màn hình quản trị, phản hồi HTTP và bản ghi kiểm toán | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-03` | Người quản lý kỳ thi tạo kỳ thi, chính sách, nhiệm vụ, mã tham gia và chạy kiểm tra sẵn sàng | Chỉ đạt trạng thái sẵn sàng khi đủ điều kiện; phiên bản/trạng thái được cập nhật đúng | Ảnh màn hình kỳ thi và phản hồi API | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-04` | Thí sinh nhập mã trên tiện ích, xác thực, xem chính sách, đồng ý và kiểm tra trước phiên | Mã hợp lệ trả chính sách; thiếu quyền/sự đồng ý bị chặn; phiên được tạo đúng thí sinh | Ảnh màn hình tiện ích và nhật ký mạng/tiến trình nền | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-05` | Kích hoạt phiên tiện ích và phát sinh sự kiện chuyển thẻ, mất tập trung, rời toàn màn hình hoặc dùng bảng tạm | Trạng thái hoạt động đúng; sự kiện/nhịp kết nối đến máy chủ và xuất hiện trên chi tiết phiên | Ảnh tiện ích, bảng điều khiển, chi tiết phiên và nhật ký WebSocket | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-06` | Chạy ứng dụng thị giác máy tính: IDLE → ENROLLMENT → MONITORING | Trạng thái chuyển đúng; đăng ký thất bại không chuyển sang giám sát; camera được giải phóng khi kết thúc | Ảnh các trạng thái của ứng dụng và nhật ký cục bộ | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-07` | Tạo một hành vi đủ ngưỡng cảnh báo thị giác máy tính | Bảng điều khiển cập nhật điểm/trạng thái; vi phạm chỉ sinh tại cạnh chuyển vào cảnh báo; ảnh chụp gắn đúng sự kiện | Ảnh bảng điều khiển/chi tiết phiên, JSONL và ảnh bằng chứng | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-08` | Ngắt mạng/WebSocket rồi phục hồi | Giao diện báo mất cập nhật thời gian thực; máy khách thử kết nối lại theo thiết kế; trạng thái hiện tại được nạp lại mà không nhân đôi sự kiện | Chụp trạng thái trước/sau, số thứ tự và nhật ký máy chủ | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-09` | Dùng tài khoản/tổ chức khác mở URL kỳ thi/phiên/bằng chứng đã biết | Không lộ tài nguyên; máy chủ trả `404` hoặc `403` theo quy tắc phạm vi | Phản hồi HTTP và nhật ký kiểm toán bảo mật | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-10` | Giám thị mở bằng chứng, nhập kết luận/ghi chú và lưu hậu kiểm | Bản hậu kiểm có người thực hiện/dấu thời gian; sự kiện vi phạm gốc không đổi | Ảnh màn hình hậu kiểm, bản ghi cơ sở dữ liệu và JSONL trước/sau | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-11` | Yêu cầu báo cáo, chạy tiến trình nền và tải HTML/PDF | Tác vụ đi qua các trạng thái hợp lệ; báo cáo hiển thị đúng tiếng Việt, diễn biến, sự kiện và ảnh | Ảnh báo cáo, bản ghi `ReportJob` và tệp đầu ra | **Chưa ghi nhận – bổ sung sau khi chạy** |
| `MT-12` | Khởi động lại container và chạy chính sách lưu trữ ở chế độ thử | Cơ sở dữ liệu/bằng chứng còn trên vùng dữ liệu; chế độ thử chỉ liệt kê, chưa xóa | Hình 5.1, nhật ký container/vùng dữ liệu và đầu ra chạy thử | **Chưa ghi nhận – bổ sung sau khi chạy** |

Mỗi lần nghiệm thu cần ghi kèm: ngày giờ; bản sửa đổi/cấu hình; hệ điều hành; CPU/RAM; camera; phiên bản Chrome/Firefox và tiện ích; cách chạy máy chủ (SQLite/Uvicorn hay Docker Compose/PostgreSQL/Redis); số phiên đồng thời; cùng điều kiện mạng. Nếu một kịch bản không thực hiện được, phải ghi “Không thực hiện” và lý do thay vì đổi thành “Đạt”.

### 6.3.7. Mẫu ghi chỉ số vận hành

Các chỉ số dưới đây khác độ chính xác/độ bao phủ/điểm F1: chúng đánh giá vận hành của hệ thống triển khai, không đánh giá độ chính xác nhận diện. Báo cáo hiện không có phép đo đủ điều kiện cho các chỉ số này, do đó giá trị được để trống để điền sau khi chạy.

| Chỉ số | Cách đo đề xuất | Điều kiện cần ghi | Kết quả |
|---|---|---|---|
| Thời gian phản hồi tham gia/chính sách | Đo từ yêu cầu đến phản hồi; báo trung vị và p95 qua tối thiểu 30 lần | Chế độ máy chủ, mạng, cơ sở dữ liệu và số phiên | **Chưa đo** |
| Độ trễ sự kiện → bảng điều khiển | Hiệu giữa dấu thời gian máy chủ nhận sự kiện và thời điểm bảng điều khiển hiển thị; báo trung vị/p95 | Loại sự kiện, WSS, Redis có/không, số bảng điều khiển | **Chưa đo** |
| Thời gian kết nối lại WebSocket | Từ lúc ngắt kết nối đến khi nhận cập nhật hợp lệ đầu tiên | Kiểu mất mạng và khoảng lùi thử lại của máy khách | **Chưa đo** |
| Thời gian sinh báo cáo | Từ `ReportJob.pending` đến `completed`; tách HTML/PDF nếu có thể | Số sự kiện/ảnh chụp và cấu hình tiến trình nền | **Chưa đo** |
| CPU/RAM ứng dụng thị giác máy tính | Ghi trung bình/đỉnh trong phiên tối thiểu 10 phút | CPU, RAM, độ phân giải camera, mô hình/điểm kiểm tra | **Chưa đo** |
| FPS webcam thực | Đo cả thu hình, suy luận và hiển thị thay vì chỉ đo trên khung hình tổng hợp | Thiết bị, độ phân giải và chu kỳ chính sách/mô hình | **Chưa đo** |
| CPU/RAM máy chủ và tiến trình nền | Ghi khi không hoạt động, khi có N phiên và khi tạo báo cáo | N, tốc độ dữ liệu giám sát, PostgreSQL/Redis | **Chưa đo** |
| Dung lượng bằng chứng mỗi phiên | Tổng JSONL, ảnh chụp và báo cáo chia cho thời lượng phiên | Thời lượng, số vi phạm, chính sách ảnh chụp | **Chưa đo** |
| Khả năng chịu tải đồng thời | Tăng N phiên có kiểm soát; theo dõi tỉ lệ lỗi, p95 và số kết nối bị ngắt | Máy chủ, tiến trình nền, vùng kết nối cơ sở dữ liệu, Redis | **Chưa đo** |

Khi có kết quả, chỉ nên kết luận trong đúng cấu hình đã đo. Ví dụ, p95 trên một máy minh họa với năm phiên không được diễn giải thành cam kết mức dịch vụ cho hàng trăm phiên. Nhật ký thô hoặc kịch bản đo nên được lưu cùng báo cáo để các con số vận hành có thể kiểm tra lại.

## 6.4. Đánh giá hiệu năng chuỗi xử lý

Phép đo hiệu năng có sẵn được chạy trên CPU, sử dụng 60 khung hình tổng hợp sau 5 khung hình khởi động. Phép đo chỉ tính chi phí suy luận và logic, không bao gồm thao tác vào/ra của webcam hoặc kết xuất giao diện. Kết quả được tổng hợp như sau:

| Thành phần | Thời gian trung bình | Tỉ lệ chi phí |
|---|---:|---:|
| Phát hiện khuôn mặt bằng MTCNN | 28,95 ms/khung hình | 67% |
| YOLOv8 đã giới hạn tần suất | 10,32 ms/khung hình | 24% |
| MediaPipe Face Landmarker | 3,45 ms/khung hình | 8% |
| Tiền xử lý | 0,21 ms/khung hình | <1% |
| Logic của bảy tín hiệu | khoảng 0,04 ms/khung hình | <1% |
| **Tổng** | **42,98 ms/khung hình** | **100%** |

Vòng lặp đo trực tiếp đạt khoảng 25,3 FPS. MTCNN là nút thắt chính; tầng trích xuất tín hiệu chiếm tỉ lệ nhỏ vì chỉ xử lý các đặc trưng dùng chung. Một lần gọi `FaceEmbedder.extract()` mất khoảng 27,6 ms nhưng mặc định chỉ chạy sau mỗi 30 giây. Vì vậy, chi phí trung bình thấp, mặc dù một khung hình có thể bị chậm tại thời điểm kiểm tra lại danh tính.

Kết quả cho thấy chuỗi xử lý đạt tốc độ gần thời gian thực trong đúng cấu hình máy và dữ liệu tổng hợp của phép đo; đây không phải cam kết FPS cho mọi thiết bị. Cần chạy lại `scripts/benchmark_fps.py` trên máy triển khai và với khung hình webcam đại diện trước khi đưa ra kết luận vận hành.

## 6.5. Thiết kế thực nghiệm 25 video

### 6.5.1. Nguồn gốc dữ liệu

Theo bản tổng hợp từ môi trường thực nghiệm bên ngoài, bộ đánh giá gồm 25 video tự quay, nhãn tham chiếu và 199.470 khung hình được đưa vào ma trận nhầm lẫn. Bản báo cáo trước mô tả thời lượng “gần một giờ ở 30 FPS”, nhưng mô tả này không nhất quán với tổng số khung hình. Do không có siêu dữ liệu video gốc trong kho mã nguồn để kiểm tra lại, báo cáo chỉ công bố số video và số khung hình đã được ghi nhận; không tiếp tục sử dụng ước lượng thời lượng nêu trên.

Các nhóm kịch bản gồm:

- Hành vi bình thường.
- Sử dụng điện thoại/vật thể cấm.
- Quay đầu hoặc nhìn chuyển hướng.
- Nhiều người trong khung hình.
- Hoạt động miệng/nói chuyện.
- Đổi người trong phiên.

Nhãn tham chiếu nhị phân được gán theo khung hình: `0` là bình thường, `1` là có ít nhất một hành vi vi phạm. Theo mô tả đi kèm số liệu, hai người thực hiện gán nhãn độc lập và trường hợp không thống nhất được phân xử bởi người thứ ba. Tuy nhiên, bộ dữ liệu gốc, lịch sử gán nhãn và chỉ số đồng thuận không có trong kho mã nguồn; do đó, quy trình này chưa thể được kiểm tra độc lập từ bản bàn giao.

### 6.5.2. Đơn vị và cách tính

Đơn vị đánh giá là **khung hình**, không phải số lượng `ViolationEvent`. Nhãn của mỗi khung hình được so với trạng thái dự đoán tại cùng thời điểm. Một khoảng cảnh báo kéo dài đóng góp nhiều khung hình dương tính dự đoán, mặc dù bộ tổng hợp chỉ sinh một sự kiện tại cạnh chuyển vào cảnh báo.

Đánh giá theo khung hình phù hợp để đo khoảng thời gian hệ thống ở trạng thái đúng hoặc sai, nhưng các khung hình liên tiếp có tương quan cao. Vì vậy, 199.470 khung hình không tương đương 199.470 mẫu độc lập. Khi chia tập huấn luyện/xác thực/kiểm thử hoặc so sánh mô hình, cần chia theo video và người tham gia thay vì trộn khung hình của cùng một video vào nhiều tập.

### 6.5.3. Phương pháp cơ sở

Phương pháp cơ sở mô phỏng chuỗi điều kiện đơn giản:

```text
if không có khuôn mặt: cảnh báo
else if nhiều khuôn mặt: cảnh báo
else if EAR thấp đủ điều kiện: cảnh báo
else if có vật thể: cảnh báo
else: bình thường
```

Phương pháp cơ sở không kết hợp đồng thời nhiều tín hiệu, không có xác minh danh tính, PnP đầy đủ hoặc vùng trễ hai cấp tương đương. Theo tài liệu thực nghiệm, phương pháp này được chạy trên cùng bộ video để tạo điểm so sánh; đầu ra dự đoán gốc không có trong bản bàn giao để kiểm tra lại.

### 6.5.4. Cấu hình thực nghiệm và cấu hình hiện tại

Tài liệu từ môi trường ngoài ghi nhận việc hiệu chỉnh ngưỡng vùng trễ, trọng số, EAR và một điểm kiểm tra YOLOv8 đã được tinh chỉnh cho điện thoại. Tệp mô hình và biểu đồ huấn luyện không có trong kho mã nguồn hiện tại. Bản bàn giao mặc định sử dụng `models/yolov8n.pt` được huấn luyện trước trên COCO, trọng số chưa chuẩn hóa và `T_enter=5,0`, `T_exit=2,5`.

Do đó, các chỉ số tại mục 6.6 là kết quả của **một cấu hình thực nghiệm bên ngoài**, không phải phép đo có thể tái lập nguyên trạng chỉ từ kho mã nguồn hiện tại. Việc tái lập cần bổ sung mã phiên bản, cấu hình, tệp mô hình, danh mục video, nhãn tham chiếu và đầu ra dự đoán.

## 6.6. Kết quả định lượng

### 6.6.1. Ma trận nhầm lẫn

|  | Dự đoán bình thường | Dự đoán vi phạm | Tổng |
|---|---:|---:|---:|
| Nhãn tham chiếu bình thường | TN = 158.970 | FP = 10.500 | 169.470 |
| Nhãn tham chiếu vi phạm | FN = 4.500 | TP = 25.500 | 30.000 |
| **Tổng** | **163.470** | **36.000** | **199.470** |

Tỉ lệ khung hình vi phạm trong nhãn tham chiếu là:

$$
\frac{30.000}{199.470}=15,04\%
$$

Bộ dữ liệu mất cân bằng theo hướng khung hình bình thường chiếm đa số; vì vậy, không thể chỉ dùng Accuracy để kết luận.

### 6.6.2. Các chỉ số suy ra

| Chỉ số | Công thức | Giá trị |
|---|---|---:|
| Accuracy | $(TP+TN)/N$ | 0,9248 |
| Độ chính xác (Precision) | $TP/(TP+FP)$ | 0,7083 |
| Độ bao phủ (Recall) | $TP/(TP+FN)$ | 0,8500 |
| F1-score | $2PR/(P+R)$ | 0,7727 |
| Specificity | $TN/(TN+FP)$ | 0,9380 |
| False Positive Rate | $FP/(TN+FP)$ | 0,0620 |

Từ ma trận trên, độ chính xác 0,7083 cho biết khoảng 70,83% khung hình được dự đoán vi phạm trùng với nhãn vi phạm; độ bao phủ 0,8500 cho biết hệ thống nhận đúng 85% số khung hình được gán nhãn vi phạm. Điểm F1 bằng 0,7727 thể hiện sự cân bằng giữa hai đại lượng này.

Tài liệu thực nghiệm nêu các ngưỡng mục tiêu: độ chính xác ≥ 0,70, độ bao phủ ≥ 0,80 và F1 ≥ 0,75; các giá trị được ghi nhận đều vượt những ngưỡng này. Tuy nhiên, do không có tài liệu đánh dấu thời điểm xác lập mục tiêu, báo cáo không khẳng định các ngưỡng đã được đăng ký trước khi thực nghiệm. Kết quả chỉ cho thấy cấu hình có tiềm năng hỗ trợ hậu kiểm trong phạm vi bộ dữ liệu đã thu thập, chưa đủ để kết luận sẵn sàng cho kỳ thi rủi ro cao hoặc quần thể người dùng rộng.

ROC-AUC và PR-AUC không được đưa vào bản sửa đổi. Hai chỉ số này cần điểm số hoặc đường cong tại nhiều ngưỡng; ma trận nhầm lẫn tại một ngưỡng không đủ để kiểm chứng các giá trị AUC từng xuất hiện trong bản cũ.

## 6.7. So sánh với phương pháp cơ sở

| Chỉ số | Phương pháp cơ sở | Hệ thống thực nghiệm | Tăng tuyệt đối | Tăng tương đối |
|---|---:|---:|---:|---:|
| Độ chính xác (Precision) | 0,6521 | 0,7083 | +0,0562 | +8,62% |
| Độ bao phủ (Recall) | 0,7230 | 0,8500 | +0,1270 | +17,57% |
| F1-score | 0,6851 | 0,7727 | +0,0876 | +12,79% |
| Specificity | 0,9128 | 0,9380 | +0,0252 | +2,76% |

Theo bảng kết quả được cung cấp, hệ thống thực nghiệm cao hơn phương pháp cơ sở ở bốn chỉ số. Mức tăng tuyệt đối lớn nhất nằm ở độ bao phủ, phù hợp với giả thuyết rằng việc kết hợp nhiều tín hiệu có trạng thái và xác minh danh tính có thể giảm bỏ sót so với chuỗi điều kiện chỉ giữ một nhánh. Do thiếu đầu ra dự đoán gốc, báo cáo không thực hiện được kiểm định thống kê cho mức chênh lệch này.

So sánh chỉ công bằng khi hai hệ thống dùng cùng đầu vào, cùng nhãn tham chiếu, cùng đơn vị khung hình và không tinh chỉnh trên tập kiểm thử. Do tệp chia tập không có trong kho mã nguồn, kết quả được trình bày như số liệu thực nghiệm đã ghi nhận và chưa thể được kiểm toán độc lập từ bản bàn giao.

## 6.8. Độ trễ phát hiện

Môi trường thực nghiệm bên ngoài ghi nhận:

| Thống kê | Độ trễ |
|---|---:|
| Trung bình | 2,3 giây |
| Nhỏ nhất | 0,1 giây |
| Lớn nhất | 8,5 giây |
| Phân vị 95 | 5,2 giây |

Độ trễ là khoảng cách giữa thời điểm bắt đầu đoạn có nhãn vi phạm và thời điểm hệ thống chuyển sang cảnh báo. Đại lượng này chịu ảnh hưởng trực tiếp của cơ chế chống dao động, cửa sổ máy trạng thái, chu kỳ mô hình và vùng trễ. Không nên diễn giải 2,3 giây như cam kết mức dịch vụ chung cho mọi tín hiệu: tín hiệu danh tính trong kho mã nguồn hiện chỉ kiểm tra lại định kỳ sau 30 giây, còn một số tín hiệu khác có thể phản ứng sau khoảng 1–2 giây.

Do không có tệp độ trễ theo từng loại sự kiện trong kho mã nguồn, báo cáo chưa thể phân tích trung vị, phân bố theo tín hiệu hoặc khoảng tin cậy.

## 6.9. Phân tích lỗi

### 6.9.1. Âm tính giả

Ma trận nhầm lẫn có 4.500 khung hình âm tính giả (FN). Tài liệu phân tích bên ngoài đã phân loại nguyên nhân cho 4.180 khung hình; 320 khung hình còn lại chưa có nhãn nguyên nhân chi tiết.

| Nguyên nhân trong phần đã phân loại | Số khung hình | Tỉ lệ trên 4.180 khung hình đã phân loại |
|---|---:|---:|
| Quay đầu nhẹ, chưa vượt điều kiện | 1.200 | 28,7% |
| Độ tương đồng danh tính nằm trong vùng biên | 800 | 19,1% |
| Nhắm mắt quá ngắn | 650 | 15,6% |
| Ánh sáng xấu | 450 | 10,8% |
| Vật thể nhỏ/ở rìa ảnh | 400 | 9,6% |
| Nguyên nhân khác | 680 | 16,3% |

Các nhóm này cho thấy độ bao phủ không chỉ phụ thuộc vào mô hình mà còn phụ thuộc định nghĩa nhãn tham chiếu. Ví dụ, nếu nhãn tham chiếu coi mọi lần quay nhẹ là vi phạm nhưng chính sách hệ thống chỉ cảnh báo sau một góc hoặc thời lượng nhất định, một phần FN bắt nguồn từ khác biệt về quy tắc đánh giá chứ không hoàn toàn là lỗi nhận diện.

### 6.9.2. Dương tính giả

Theo bảng phân tích được cung cấp, 10.500 khung hình dương tính giả (FP) được phân loại như sau:

| Nguyên nhân | Số khung hình | Tỉ lệ FP |
|---|---:|---:|
| Quay đầu tự nhiên | 3.500 | 33,3% |
| Nhắm mắt tự nhiên/mệt | 2.100 | 20,0% |
| Phát hiện nhầm vật thể | 2.800 | 26,7% |
| Ánh sáng hoặc góc mặt | 1.200 | 11,4% |
| Khác | 900 | 8,6% |

Ước lượng góc quay đầu và phát hiện vật thể đóng góp phần lớn vào FP. Điều này phù hợp với giới hạn quan sát: quay đầu không đồng nghĩa với nhìn tài liệu, còn YOLO được huấn luyện trước hoặc tinh chỉnh vẫn có thể nhận nhầm vật thể. Vì vậy, bảng điều khiển cần hiển thị ảnh và các tín hiệu đóng góp thay vì chỉ hiển thị nhãn cuối.

## 6.10. Đe dọa đến tính hợp lệ

### 6.10.1. Tính hợp lệ nội tại

- Tệp thực nghiệm gốc không có trong kho mã nguồn nên không thể chạy lại toàn bộ đánh giá trong môi trường hiện tại.
- Chưa có mã phiên bản, hạt giống ngẫu nhiên và cấu hình đầy đủ của lần thực nghiệm.
- Chưa có bằng chứng về cách chia video khi tinh chỉnh mô hình; nếu khung hình của cùng một video xuất hiện trong cả tập huấn luyện và tập kiểm thử, chỉ số có thể lạc quan hơn thực tế.
- Nhãn tham chiếu nhị phân gộp nhiều loại vi phạm, che khuất khác biệt giữa từng tín hiệu.
- Chưa báo Cohen's kappa hoặc thước đo đồng thuận giữa người gán nhãn.

### 6.10.2. Tính hợp lệ bên ngoài

- 25 video chưa đại diện đầy đủ cho camera, ánh sáng, màu da, kính, khẩu trang và thiết bị khác nhau.
- Dữ liệu do một nhóm nhỏ tự quay có thể khác hành vi trong kỳ thi thật.
- Chỉ số ở mức khung hình bị chi phối bởi độ dài đoạn và tương quan giữa các khung hình liên tiếp.
- Kết quả không chứng minh khả năng chống sửa đổi máy khách, camera ảo, phát lại video hoặc nội dung giả mạo.

### 6.10.3. Khả năng tái lập cần bổ sung

Một gói thực nghiệm hoàn chỉnh nên lưu:

```text
evaluation/
├── manifest.csv
├── labels/<clip>.labels.json
├── splits.json
├── config/fusion.yaml
├── model/checkpoint + hash
├── predictions/<clip>.jsonl
├── metrics.json
├── environment.txt
└── generate_figures.py
```

Đối với dữ liệu nhạy cảm không thể công khai, có thể lưu hàm băm và danh mục tệp để chứng minh các tệp dùng trong tính toán không bị thay đổi.

## 6.11. Đánh giá theo tiêu chí nghiệm thu

| Nhóm yêu cầu | Bằng chứng | Kết luận |
|---|---|---|
| Chuỗi xử lý và bảy tín hiệu | Kiểm thử đơn vị, khởi tạo mô hình và tích hợp video | Đạt về chức năng |
| Tổng hợp rủi ro, giải thích và báo cáo | Kiểm thử trạng thái, cạnh chuyển và tính nhất quán báo cáo | Đạt về chức năng |
| Xác thực, RBAC và cô lập tổ chức | Kiểm thử hồi quy API, WebSocket và bảo mật | Đạt trong phạm vi kiểm thử |
| Tiện ích mở rộng | 8 ca kiểm thử Node và rà soát mã nguồn | Đạt phần logic tự động; cần bổ sung kiểm thử trên trình duyệt thực |
| Hiệu năng thị giác máy tính cục bộ | Phép đo CPU tổng hợp khoảng 25,3 FPS | Đạt trên máy đo, không khái quát cho mọi thiết bị |
| Độ chính xác/độ bao phủ/F1 mục tiêu | 0,7083 / 0,8500 / 0,7727 | Vượt ngưỡng nêu trong tài liệu trên cấu hình 25 video bên ngoài; chưa tái lập |
| Tái lập thực nghiệm | Tệp gốc không có trong kho mã nguồn | Chưa đạt |
| Trình duyệt khóa/chứng thực từ xa | Ngoài phạm vi | Không đánh giá |

## 6.12. Kết chương

Chương 6 đã tách biệt kiểm thử phần mềm, đánh giá hoạt động hệ thống và đánh giá độ chính xác của thành phần thị giác máy tính. Bộ kiểm thử Python đạt 309/309 ca ở lần chạy toàn bộ thứ hai, nhưng lần đầu có một ca lỗi không tái hiện khi chạy riêng; bộ kiểm thử tiện ích mở rộng đạt 8/8 ca. Các luồng quản trị, tham gia, thời gian thực, bằng chứng, hậu kiểm và báo cáo đạt trong phạm vi kiểm thử đã mô tả, song kết quả dao động của ca sắp xếp nhật ký cần tiếp tục được theo dõi. Phép đo CPU tổng hợp ghi nhận khoảng 25,3 FPS trong cấu hình đo cụ thể. Bảng số liệu của thực nghiệm 25 video với 199.470 khung hình cho độ chính xác 0,7083, độ bao phủ 0,8500 và điểm F1 bằng 0,7727, cao hơn phương pháp cơ sở được báo cáo.

Các số liệu thực nghiệm được giữ như kết quả đã ghi nhận từ môi trường ngoài, đồng thời báo cáo công khai ba giới hạn: tệp thực nghiệm chưa có trong kho mã nguồn, cấu hình hiện tại không hoàn toàn trùng với cấu hình tạo số liệu và bộ dữ liệu còn nhỏ. Chương 7 sử dụng kết quả này trong đúng phạm vi trên, không mở rộng thành tuyên bố sẵn sàng triển khai cho mọi kỳ thi.
