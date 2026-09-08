# Chương 3. Khảo sát và phân tích yêu cầu

## 3.1. Tổng quan

Chương 2 đã trình bày các kỹ thuật nền tảng. Chương này khảo sát những hướng tiếp cận đang được sử dụng trong giám sát thi trực tuyến, phân tích một dự án mã nguồn mở làm đối chứng và chuyển các khoảng trống tìm được thành yêu cầu cụ thể cho hệ thống.

Phạm vi khảo sát không nhằm khẳng định một sản phẩm là “tốt nhất”, vì mỗi giải pháp phục vụ mô hình thi, chính sách và ngân sách khác nhau. Mục tiêu của chương là xác định các năng lực cần thiết, những giới hạn không thể giải quyết chỉ bằng một mô hình thị giác máy tính và vị trí đóng góp của đồ án.

## 3.2. Khảo sát nhóm giải pháp thương mại

Các nền tảng thương mại thường cung cấp ba mô hình dịch vụ: giám sát tự động, ghi lại để con người xem sau và giám sát trực tiếp. Chức năng được cấu hình theo từng kỳ thi, có thể gồm xác minh người dự thi, ghi hình webcam, microphone hoặc màn hình, hạn chế thao tác trình duyệt, phát hiện sự kiện và tạo báo cáo.

### 3.2.1. Proctorio

Theo tài liệu sản phẩm chính thức, Proctorio cung cấp các nhóm thiết lập ghi dữ liệu, xác minh và hạn chế môi trường thi. Tùy cấu hình của đơn vị tổ chức, sản phẩm có thể ghi video, âm thanh, màn hình hoặc lưu lượng web; xác minh danh tính; yêu cầu chế độ toàn màn hình; hạn chế chuyển thẻ, bảng tạm và một số thao tác khác. Giải pháp sử dụng tiện ích mở rộng trên trình duyệt máy tính và chỉ kích hoạt trong phiên thi đã được cấu hình [16], [17].

Điểm đáng chú ý đối với đồ án là việc tách chính sách kỳ thi khỏi ứng dụng phía thí sinh. Mỗi kỳ thi có thể yêu cầu những năng lực khác nhau thay vì mọi phiên đều bật toàn bộ quyền. Tuy nhiên, đây là nền tảng đóng; tài liệu công khai không mô tả đầy đủ logic nội bộ để tái hiện thuật toán hoặc hiệu chỉnh theo mục tiêu nghiên cứu của đồ án.

### 3.2.2. Honorlock

Honorlock cung cấp BrowserGuard để hạn chế hoặc đánh dấu việc truy cập trang web, chuyển thẻ, sử dụng ứng dụng, phím tắt và hành vi thu nhỏ cửa sổ; sản phẩm cũng có thể ghi màn hình trong phiên thi [18]. Mô hình này cho thấy giám sát trình duyệt là một nguồn tín hiệu riêng, bổ sung cho webcam và không nên bị đồng nhất với kết quả thị giác máy tính.

### 3.2.3. ProctorU/Meazure Learning

Nền tảng ProctorU của Meazure Learning cung cấp các mức dịch vụ từ ghi hình để hậu kiểm đến giám sát trực tiếp có can thiệp [19]. Khác biệt chính so với mô hình hoàn toàn tự động là con người tham gia xác minh, theo dõi và xử lý sự cố. Điều này củng cố nguyên tắc của đồ án: thuật toán nên hỗ trợ ưu tiên và giải thích bằng chứng; quyết định cuối cùng thuộc về giám thị hoặc đơn vị tổ chức.

### 3.2.4. Nhận xét từ nhóm sản phẩm thương mại

Các sản phẩm thương mại cho thấy một hệ thống hoàn chỉnh cần nhiều hơn một mô hình phát hiện hành vi. Những năng lực thường gặp gồm chính sách theo kỳ thi, kiểm tra thiết bị, kiểm soát trình duyệt, giám sát thời gian thực, hậu kiểm và báo cáo. Việc tái tạo toàn bộ phạm vi của các sản phẩm thương mại không phù hợp với nguồn lực của đồ án. Vì vậy, hệ thống đề xuất lựa chọn một tập chức năng có thể kiểm chứng bằng mã nguồn và công bố rõ các giới hạn.

## 3.3. Khảo sát dự án mã nguồn mở đối chứng

Đồ án sử dụng dự án `AarambhTech/exam-cheating-detection` làm nguồn tham khảo và phương pháp cơ sở ở mức ý tưởng, không sao chép mã nguồn [20]. Dự án này kết hợp OpenCV, MediaPipe, MTCNN và YOLO để quan sát khuôn mặt, mắt, miệng và vật thể từ webcam.

Ưu điểm của giải pháp tham khảo là dễ tiếp cận, chạy cục bộ và minh họa được cách ghép nhiều thư viện CV. Qua rà soát mã nguồn và so sánh kỹ thuật, đồ án nhận thấy các hạn chế sau:

- Một số điều kiện được xử lý bằng chuỗi `if-elif`, làm mất thông tin khi nhiều bất thường xảy ra đồng thời.
- Các ngưỡng dựa trên số khung hình hoặc khoảng cách điểm ảnh phụ thuộc vào tốc độ khung hình, độ phân giải và khoảng cách đến camera.
- Độ mở miệng chưa được chuẩn hóa đầy đủ; một số điểm mốc cần được xác minh lại theo API MediaPipe thực tế.
- Phần ước lượng hướng nhìn không cho ra yaw/pitch/roll theo mô hình hình học 3D.
- Không có bước tạo véc-tơ đặc trưng khuôn mặt để kiểm tra lại danh tính trong suốt phiên.
- Chưa có lớp nền tảng nhiều tổ chức, phân quyền theo kỳ thi, bảng điều khiển WebSocket và quy trình quản lý bằng chứng, hậu kiểm, báo cáo tương đương hệ thống đề xuất.

Phân tích chi tiết từng khác biệt kỹ thuật được lưu trong tài liệu nội bộ `docs/SO_SANH_KY_THUAT_TUAN4.md` [24].

## 3.4. So sánh định hướng giải pháp

| Tiêu chí | Sản phẩm thương mại | Dự án mã nguồn mở đối chứng | Hệ thống của đồ án |
|---|---|---|---|
| Minh bạch thuật toán | Hạn chế do nền tảng đóng | Có thể đọc mã nguồn | Mã nguồn và cấu hình được quản lý trong kho mã nguồn |
| Webcam/CV | Có, tùy sản phẩm và chính sách | Một số tín hiệu đơn lẻ | Bảy tín hiệu và chuỗi xử lý dùng chung |
| Xử lý theo thời gian | Không công bố đầy đủ | Chủ yếu ngưỡng/bộ đếm đơn giản | Debounce, cửa sổ trượt, state machine hai cấp |
| Xác thực trong phiên | Có thể có, chi tiết tùy sản phẩm | Không kiểm tra liên tục bằng véc-tơ đặc trưng | Đăng ký khuôn mặt, kiểm tra sự hiện diện sống cơ bản và xác minh lại định kỳ |
| Toàn vẹn trình duyệt | Thường có | Không phải trọng tâm | Tiện ích mở rộng và điểm toàn vẹn tách khỏi rủi ro CV |
| Nhiều tổ chức và phân quyền | Có | Không | RBAC, phạm vi tổ chức và nhiệm vụ theo kỳ thi |
| Giám sát thời gian thực | Có | Chủ yếu hiển thị cục bộ | Bảng điều khiển WebSocket theo kỳ thi |
| Bằng chứng và hậu kiểm | Có | Báo cáo cơ bản | JSONL, ảnh chụp, hậu kiểm sự cố và tác vụ báo cáo |
| Khả năng triển khai quy mô lớn | Sản phẩm hoàn chỉnh | Không đặt mục tiêu | Mức đồ án/triển khai có kiểm soát; còn giới hạn |
| Khả năng kiểm thử và thay đổi thuật toán | Không kiểm soát mã nguồn | Có nhưng kiến trúc đơn giản | Giao diện lập trình, cấu hình tập trung và kiểm thử nhiều tầng |

Từ bảng so sánh, đồ án không đặt mục tiêu cạnh tranh về quy mô với nền tảng thương mại. Giá trị chính nằm ở kiến trúc có thể giải thích, kiểm thử và phục vụ nghiên cứu, đồng thời mở rộng một chương trình webcam đơn máy bằng lớp nền tảng vận hành.

## 3.5. Xác định tác nhân của hệ thống

Hệ thống có năm nhóm tác nhân chính:

| Tác nhân | Phạm vi trách nhiệm |
|---|---|
| System Admin | Quản lý nền tảng, tổ chức, hạn mức, chính sách cơ sở, vận hành và nhật ký toàn cục; không mặc nhiên được xem bằng chứng |
| Organization Admin | Quản lý hồ sơ, thành viên, lời mời, chính sách và nhật ký kiểm toán của một tổ chức |
| Exam Manager | Tạo kỳ thi; với nhiệm vụ `owner/manager` có thể cấu hình, phân công và vận hành kỳ thi tương ứng |
| Proctor | Theo dõi bảng điều khiển, xem bằng chứng, hậu kiểm sự cố, kết thúc phiên và xuất báo cáo theo nhiệm vụ được giao |
| Thí sinh | Xác thực/tham gia đúng kỳ thi, cấp quyền cần thiết và gửi dữ liệu của chính phiên |

Một tài khoản có thể thuộc nhiều tổ chức nhưng tại một thời điểm chỉ thao tác trong tổ chức đang hoạt động. Quyền trên kỳ thi không được suy ra từ vai trò chung của tài khoản mà từ `ExamAssignment` của đúng kỳ thi.

## 3.6. Yêu cầu chức năng

### 3.6.1. Xác thực và tài khoản

| Mã | Yêu cầu |
|---|---|
| FR-AUTH-01 | Hệ thống cho phép nhân sự đăng nhập và đăng xuất bằng phiên được bảo vệ. |
| FR-AUTH-02 | System Admin phải hoàn tất MFA trước khi vai trò hệ thống có hiệu lực. |
| FR-AUTH-03 | Hệ thống phân biệt token nhân sự, token phiên thí sinh, device token và WebSocket ticket. |
| FR-AUTH-04 | Thay đổi trạng thái tài khoản, membership hoặc assignment phải làm quyền cũ mất hiệu lực. |
| FR-AUTH-05 | Hệ thống hỗ trợ thí sinh tham gia theo chế độ thủ công hoặc Google OIDC tùy policy kỳ thi. |

### 3.6.2. Quản lý tổ chức và chính sách

| Mã | Yêu cầu |
|---|---|
| FR-ORG-01 | System Admin quản lý tổ chức, trạng thái, hạn mức phiên đồng thời và thời hạn lưu trữ trong phạm vi được cấp. |
| FR-ORG-02 | Organization Admin quản lý hồ sơ tổ chức, thành viên, vai trò, lời mời và nhật ký kiểm toán. |
| FR-ORG-03 | Người dùng thuộc nhiều tổ chức có thể chuyển tổ chức đang hoạt động một cách an toàn. |
| FR-ORG-04 | Chính sách hiệu lực phải được xác định theo thứ tự chính sách cơ sở của nền tảng → tổ chức → kỳ thi; cấp dưới không được làm yếu yêu cầu bắt buộc. |
| FR-ORG-05 | System Admin chỉ được đọc bằng chứng khi có quyền ngoại lệ đã được phê duyệt, thuộc đúng tổ chức, còn hiệu lực và chỉ cho phép đọc. |

### 3.6.3. Quản lý kỳ thi

| Mã | Yêu cầu |
|---|---|
| FR-EXAM-01 | Exam Manager tạo kỳ thi và trở thành owner của kỳ thi đó. |
| FR-EXAM-02 | Kỳ thi hỗ trợ vòng đời `draft`, `scheduled`, `open`, `closed`, `archived` và chỉ cho phép chuyển trạng thái hợp lệ. |
| FR-EXAM-03 | Mã tham gia phải có thời hạn, có thể xoay và không tự thay đổi lifecycle ngoài ý muốn. |
| FR-EXAM-04 | Người sở hữu hoặc quản lý phân công `owner`, `manager`, `proctor` với trạng thái và thời hạn cụ thể. |
| FR-EXAM-05 | Hành động trên giao diện và máy chủ phải dựa trên năng lực được cấp trong từng kỳ thi. |
| FR-EXAM-06 | Cập nhật kỳ thi phải hỗ trợ khóa lạc quan để phát hiện chỉnh sửa đồng thời. |
| FR-EXAM-07 | Hệ thống cung cấp danh sách kiểm tra mức độ sẵn sàng dựa trên lịch, chính sách, mã tham gia, nhân sự và hạn mức. |

### 3.6.4. Tham gia và giám sát phiên thi

| Mã | Yêu cầu |
|---|---|
| FR-SESSION-01 | Thí sinh chỉ được tham gia kỳ thi đang mở, bằng mã còn hạn và với chính sách hiệu lực đã được xác định. |
| FR-SESSION-02 | Tiện ích mở rộng kiểm tra phiên bản, sự đồng ý và quyền camera/microphone/chia sẻ màn hình theo chính sách trước khi giám sát. |
| FR-CV-01 | Ứng dụng máy tính để bàn xử lý webcam thành đủ bảy `SignalResult` theo giao diện chung. |
| FR-CV-02 | Bước đăng ký thu thập nhiều khung hình, yêu cầu kiểm tra sự hiện diện sống cơ bản nếu được cấu hình và tạo véc-tơ tham chiếu. |
| FR-CV-03 | Mỗi tín hiệu phải ổn định dữ liệu theo thời gian trước khi thay đổi trạng thái. |
| FR-CV-04 | Bộ tổng hợp rủi ro tính `risk_score` từ cấu hình, áp dụng vùng trễ cấp phiên và chỉ sinh sự kiện tại cạnh chuyển vào cảnh báo. |
| FR-BROWSER-01 | Tiện ích mở rộng ghi nhận trạng thái tập trung/chuyển thẻ, toàn màn hình, bảng tạm, camera, microphone, chia sẻ màn hình và trạng thái giám sát. |
| FR-BROWSER-02 | Máy chủ tự xác định mức nghiêm trọng và điểm toàn vẹn từ sự kiện trình duyệt theo chính sách, không tin điểm do máy khách tự khai báo. |
| FR-SESSION-03 | Hệ thống hỗ trợ heartbeat, trạng thái `pending/active/disconnected/ended` và lý do mất kết nối. |

### 3.6.5. Bảng điều khiển, bằng chứng và báo cáo

| Mã | Yêu cầu |
|---|---|
| FR-RT-01 | Dashboard nhận cập nhật phiên theo thời gian thực qua WebSocket trong đúng phạm vi kỳ thi. |
| FR-RT-02 | Máy chủ kiểm tra lược đồ, sự hiện diện của đủ bảy tín hiệu, thời gian, rủi ro, trạng thái, mức nghiêm trọng và mức đóng góp trước khi chấp nhận dữ liệu CV. |
| FR-EVID-01 | Hệ thống lưu siêu dữ liệu, tín hiệu, chuyển trạng thái, diễn biến điểm rủi ro, sự kiện trình duyệt, vi phạm và ảnh chụp theo phiên. |
| FR-EVID-02 | Ảnh chụp phải được giới hạn định dạng và kích thước, kiểm tra nội dung và lưu bằng tên do máy chủ sinh. |
| FR-REVIEW-01 | Giám thị có thể ghi trạng thái và nhận xét hậu kiểm mà không sửa sự kiện máy gốc. |
| FR-REPORT-01 | Hệ thống sinh báo cáo HTML/PDF từ dữ liệu phiên, kể cả khi thiếu một phần nhật ký. |
| FR-REPORT-02 | Tác vụ báo cáo chạy nền và cho biết trạng thái xử lý, lỗi hoặc kết quả. |
| FR-RET-01 | Tác vụ lưu trữ hỗ trợ chế độ chạy thử trước khi xóa hoặc ẩn danh dữ liệu hết hạn và phải ghi nhật ký kiểm toán. |

## 3.7. Yêu cầu phi chức năng

| Mã | Nhóm | Yêu cầu |
|---|---|---|
| NFR-SEC-01 | Bảo mật | Mọi REST, WebSocket và file download phải kiểm tra authentication, tenant và resource scope tại backend. |
| NFR-SEC-02 | Bảo mật | Không đặt bearer token dài hạn trong URL WebSocket; ticket browser phải ngắn hạn và dùng một lần. |
| NFR-SEC-03 | Bảo mật | Message, ảnh và metadata từ client phải được coi là đầu vào không tin cậy và được kiểm tra chặt. |
| NFR-SEC-04 | Bảo mật | Giao diện phải hạn chế XSS, clickjacking, MIME sniffing và rò rỉ referrer bằng CSP/security header phù hợp. |
| NFR-PRIV-01 | Riêng tư | Không truyền video liên tục; chỉ gửi telemetry theo lô và snapshot tại sự kiện cần bằng chứng. |
| NFR-PRIV-02 | Riêng tư | Không lưu mã truy cập/mã làm mới của Google; chỉ lưu thuộc tính OIDC tối thiểu và dạng băm của mã xác thực khi có thể. |
| NFR-REL-01 | Tin cậy | Một detector lỗi tạm thời không được làm crash toàn bộ phiên CV. |
| NFR-REL-02 | Tin cậy | Client mất mạng phải được đánh dấu disconnected; desktop CV vẫn có khả năng ghi log/báo cáo cục bộ. |
| NFR-PERF-01 | Hiệu năng | Detector nền dùng chung chỉ chạy một lần cho mỗi frame; YOLO được throttle theo thời gian. |
| NFR-PERF-02 | Hiệu năng | Telemetry mạng được gửi theo lô, mặc định khoảng một giây, không commit database ở mọi frame. |
| NFR-MAIN-01 | Bảo trì | Ngưỡng và trọng số thuật toán phải tập trung trong cấu hình có kiểm tra hợp lệ. |
| NFR-MAIN-02 | Bảo trì | Signal Extractor, data schema và authorization phải có interface/quy tắc tập trung và kiểm thử hồi quy. |
| NFR-EXPL-01 | Giải thích | Mỗi cảnh báo phải truy được risk score, state, tín hiệu đóng góp, thời gian và evidence liên quan. |
| NFR-PORT-01 | Triển khai | Backend có thể chạy local development hoặc Docker Compose; dữ liệu bền vững qua volume phù hợp. |
| NFR-TEST-01 | Kiểm thử | Chức năng lõi phải có unit/integration test; metric CV phải công bố dataset, ground truth và đơn vị đánh giá. |

## 3.8. Ràng buộc và giả định

Các ràng buộc chính của đồ án gồm:

- Các mô hình CV nền đã được huấn luyện trước; nguồn lực của đồ án không cho phép huấn luyện toàn bộ mô hình từ đầu.
- Tham số nội tại của camera không được hiệu chuẩn riêng cho mọi thiết bị, vì vậy PnP sử dụng ma trận camera xấp xỉ.
- Ứng dụng CV và tiện ích mở rộng là hai nhánh phía máy khách; cầu nối native messaging để hợp nhất hoàn toàn hai nhánh trong cùng một phiên chưa thuộc phiên bản hiện tại.
- Connection manager WebSocket hoạt động in-process khi không cấu hình Redis; triển khai nhiều worker phải bật Redis lease/pub-sub như cấu hình Docker Compose hoặc dùng message broker tương đương.
- Dữ liệu tổng hợp dùng để kiểm thử bảng điều khiển và báo cáo không thay thế video thật trong đánh giá độ chính xác.
- Bộ 25 video, nhãn tham chiếu và tệp kết quả đánh giá nằm ở môi trường thực nghiệm khác, không có trong kho mã nguồn bàn giao hiện tại.
- Kết quả tự động chỉ là chỉ báo phục vụ hậu kiểm, không phải kết luận kỷ luật.

## 3.9. Tiêu chí nghiệm thu và truy vết

Các yêu cầu được coi là hoàn thành khi có phần cài đặt và bằng chứng kiểm tra tương ứng. Bảng 3.1 tóm tắt tuyến truy vết ở cấp nhóm.

| Nhóm yêu cầu | Giải pháp/đóng góp | Thành phần cài đặt | Bằng chứng đánh giá |
|---|---|---|---|
| `FR-CV-*`, `NFR-PERF-*` | Chuỗi xử lý dùng chung và bảy tín hiệu | `src/perception`, `src/signals`, `src/orchestrator.py` | Kiểm thử đơn vị, khởi tạo mô hình, tích hợp video và đo hiệu năng |
| `FR-CV-04`, `NFR-EXPL-01` | Máy trạng thái và tổng hợp rủi ro hai cấp | `src/fusion`, `config/fusion.yaml` | Kiểm thử chuyển trạng thái, cạnh chuyển, nhiều tín hiệu và tính nhất quán báo cáo |
| `FR-BROWSER-*`, `FR-RT-*` | Tiện ích mở rộng và kiểm tra WebSocket | `extension/`, `backend/routers/ws.py` | Kiểm thử tiện ích, tích hợp WebSocket và xác thực |
| `FR-AUTH-*`, `FR-ORG-*`, `FR-EXAM-*` | RBAC và phạm vi tổ chức/tài nguyên | `backend/auth.py`, `backend/authorization.py`, `backend/policies.py` | Kiểm thử API, MFA, chính sách, cô lập tổ chức và nhiệm vụ |
| `FR-EVID-*`, `FR-REPORT-*`, `FR-RET-01` | Dữ liệu lai và vòng đời bằng chứng | `backend/session_materializer.py`, `src/reporting`, `scripts/report_worker.py`, `scripts/cleanup_retention.py` | Kiểm thử ảnh chụp, đường dẫn, báo cáo và tác vụ nền |
| Chỉ số CV | Đánh giá trên 25 video | Chuỗi xử lý/phương pháp cơ sở trong môi trường thực nghiệm | Ma trận nhầm lẫn, Precision, Recall, F1-score và độ trễ tại Chương 6 |

Chi tiết giải pháp được trình bày trong Chương 4, quá trình cài đặt trong Chương 5 và kết quả đánh giá trong Chương 6.

## 3.10. Kết chương

Chương 3 cho thấy các nền tảng thương mại có quy trình vận hành tương đối hoàn chỉnh nhưng khó kiểm chứng thuật toán, trong khi dự án mã nguồn mở thuận lợi cho khảo sát nhưng thường thiếu xử lý theo thời gian, phân quyền và vòng đời quản lý bằng chứng. Từ kết quả khảo sát, chương đã xác định năm tác nhân, các yêu cầu chức năng theo từng miền, yêu cầu phi chức năng, ràng buộc và tuyến truy vết.

Chương 4 tiếp theo trình bày các giải pháp và đóng góp được thiết kế để đáp ứng những yêu cầu này, trong đó mỗi đóng góp được phân tích theo bài toán, giải pháp và kết quả đạt được.
