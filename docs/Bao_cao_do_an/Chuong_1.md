# Chương 1. Giới thiệu đề tài

## 1.1. Đặt vấn đề

Thi trực tuyến ngày càng được sử dụng trong giáo dục, tuyển dụng và các chương trình cấp chứng chỉ. Hình thức này giúp giảm chi phí tổ chức, mở rộng phạm vi tiếp cận và tạo điều kiện cho người học tham gia từ nhiều địa điểm. Tuy nhiên, khi thí sinh làm bài trên thiết bị cá nhân và ngoài không gian thi truyền thống, đơn vị tổ chức khó duy trì mức độ giám sát tương đương một phòng thi trực tiếp.

Các hành vi cần được quan tâm không chỉ gồm những vi phạm rõ ràng như rời khỏi vị trí, xuất hiện người thứ hai hoặc sử dụng điện thoại, mà còn gồm các tình huống khó quan sát hơn: thường xuyên nhìn ra ngoài màn hình, trao đổi với người khác, thay người giữa kỳ thi, chuyển tab, thoát chế độ toàn màn hình, sử dụng clipboard hoặc vô hiệu hóa thiết bị giám sát. Một giám thị theo dõi đồng thời nhiều thí sinh khó quan sát liên tục toàn bộ các dấu hiệu này. Sau kỳ thi, việc chỉ dựa vào trí nhớ của giám thị cũng không cung cấp đủ dữ liệu để xem xét một sự cố theo cách nhất quán.

Giám sát tự động có thể hỗ trợ bằng cách thu thập tín hiệu, đánh dấu những khoảng thời gian bất thường và cung cấp bằng chứng để con người xem xét. Tuy nhiên, đây không phải bài toán phân loại một ảnh đơn giản. Dữ liệu webcam chịu ảnh hưởng của ánh sáng, góc đặt camera, đặc điểm khuôn mặt, kính, che khuất và năng lực phần cứng. Một lần chớp mắt hoặc quay đầu ngắn không đồng nghĩa với gian lận. Tương tự, một lần mất focus có thể xuất phát từ thông báo hệ thống thay vì chủ ý rời bài thi. Nếu mọi tín hiệu tức thời đều trở thành cảnh báo, số lượng báo động giả sẽ làm giảm giá trị của hệ thống và gây bất lợi cho thí sinh.

Bài toán còn có khía cạnh vận hành. Một giải pháp sử dụng trong thực tế cần quản lý nhiều tổ chức, kỳ thi, giám thị và phiên thi; truyền trạng thái theo thời gian thực; kiểm soát quyền truy cập đến dữ liệu nhạy cảm; lưu ảnh và sự kiện có thể truy vết; và sinh báo cáo sau kỳ thi. Việc truyền video liên tục lên server làm tăng băng thông và phạm vi xử lý dữ liệu cá nhân, trong khi chỉ chạy một ứng dụng cục bộ lại không hỗ trợ giám sát tập trung. Do đó, hệ thống cần cân bằng giữa xử lý tại thiết bị, quản lý tập trung, khả năng giải thích và quyền riêng tư.

Từ các vấn đề trên, đồ án lựa chọn đề tài **“Hệ thống giám sát thi trực tuyến bằng thị giác máy tính”**. Hệ thống kết hợp bảy tín hiệu thị giác máy tính, các sự kiện toàn vẹn trình duyệt và một nền tảng quản lý nhiều tổ chức. Mục tiêu của hệ thống là hỗ trợ giám thị phát hiện và xem xét sự kiện đáng ngờ, không tự động kết luận thí sinh gian lận. Quyết định cuối cùng vẫn thuộc về người có thẩm quyền dựa trên quy chế thi, ngữ cảnh và bằng chứng liên quan.

## 1.2. Động lực và khoảng trống cần giải quyết

Các giải pháp giám sát thi hiện có có thể được chia thành hai nhóm. Nhóm sản phẩm thương mại thường cung cấp nhiều chức năng như kiểm tra thiết bị, khóa hoặc theo dõi trình duyệt, ghi hình và hỗ trợ giám thị. Ưu điểm của nhóm này là quy trình vận hành tương đối hoàn chỉnh. Tuy nhiên, thuật toán phát hiện thường không được công bố đầy đủ; khả năng điều chỉnh, kiểm chứng độc lập và triển khai theo yêu cầu riêng có thể bị hạn chế.

Nhóm dự án mã nguồn mở và nghiên cứu học thuật tạo điều kiện khảo sát thuật toán và tái sử dụng mã nguồn. Một số dự án kết hợp OpenCV, MediaPipe, MTCNN và YOLO để nhận biết khuôn mặt, trạng thái mắt, chuyển động miệng hoặc vật thể. Tuy vậy, nhiều giải pháp dừng ở một chương trình cục bộ, xử lý từng điều kiện bằng chuỗi `if-elif` và ghi một nhãn cho mỗi khung hình. Cách làm này có bốn hạn chế chính:

1. Kết quả của một frame dễ bị ảnh hưởng bởi nhiễu và không biểu diễn được thời lượng hành vi.
2. Nhiều tín hiệu xảy ra đồng thời không được kết hợp theo mức độ quan trọng.
3. Một số phép đo dựa trên độ lệch pixel hoặc khoảng cách tuyệt đối phụ thuộc độ phân giải, FPS và vị trí khuôn mặt.
4. Ứng dụng thiếu lớp quản lý kỳ thi, phân quyền, theo dõi thời gian thực, lưu bằng chứng và đánh giá sau sự kiện.

Đồ án giải quyết khoảng trống này theo hướng thiết kế hệ thống thay vì chỉ ghép các mô hình nhận diện. Các mô hình pretrained được xem là thành phần nền; đóng góp tập trung vào kiến trúc pipeline, hợp đồng dữ liệu, xử lý theo thời gian, tổng hợp rủi ro, xác thực danh tính trong phiên, tích hợp trình duyệt, phân quyền theo tài nguyên và chu trình quản lý bằng chứng.

## 1.3. Mục tiêu của đề tài

### 1.3.1. Mục tiêu tổng quát

Xây dựng một hệ thống giám sát thi trực tuyến có khả năng thu thập và tổng hợp nhiều tín hiệu bất thường, hỗ trợ giám thị theo dõi phiên thi theo thời gian thực và xem lại bằng chứng sau kỳ thi; đồng thời bảo đảm hệ thống có cấu trúc mô-đun, có thể kiểm thử, cấu hình và mở rộng.

### 1.3.2. Mục tiêu cụ thể

Để đạt mục tiêu tổng quát, đồ án xác định các mục tiêu cụ thể sau:

- Xây dựng tầng nhận thức dùng chung để phát hiện khuôn mặt, trích xuất landmark và phát hiện vật thể mà không chạy lặp cùng một model cho từng tín hiệu.
- Cài đặt bảy tín hiệu gồm `FACE_PRESENCE`, `MULTI_FACE`, `EYE_STATE`, `MOUTH_STATE`, `OBJECT_PRESENCE`, `HEAD_POSE` và `IDENTITY` theo một interface thống nhất.
- Ước lượng yaw, pitch và roll bằng bài toán Perspective-n-Point thay cho phép so sánh độ lệch pixel đơn giản.
- Đăng ký và kiểm tra lại danh tính bằng face embedding trong suốt phiên thi; kết hợp thử thách chớp mắt cơ bản trong bước enrollment.
- Xây dựng state machine theo cửa sổ thời gian cho từng tín hiệu và Risk Fusion Engine có trọng số, hysteresis hai cấp và khả năng giải thích tín hiệu đóng góp.
- Xây dựng browser extension theo dõi những sự kiện liên quan đến focus, tab, toàn màn hình, clipboard, camera, microphone và chia sẻ màn hình theo chính sách kỳ thi.
- Xây dựng backend FastAPI và dashboard để quản lý tổ chức, thành viên, kỳ thi, phiên thi, sự cố và báo cáo; truyền cập nhật bằng WebSocket.
- Thiết kế phân quyền theo vai trò, tổ chức và assignment của từng kỳ thi; hạn chế quyền truy cập đến bằng chứng nhạy cảm và ghi nhật ký hoạt động.
- Tổ chức dữ liệu dưới dạng kết hợp cơ sở dữ liệu quan hệ với JSONL và ảnh snapshot, phục vụ đồng thời truy vấn trạng thái mới nhất và tái dựng timeline.
- Đánh giá giải pháp bằng kiểm thử phần mềm, kiểm thử tích hợp và bộ 25 video có ground truth được thực hiện trong môi trường đánh giá riêng.

## 1.4. Đối tượng và phạm vi nghiên cứu

### 1.4.1. Đối tượng nghiên cứu

Đối tượng nghiên cứu của đồ án gồm:

- Các kỹ thuật phát hiện khuôn mặt, landmark khuôn mặt, trạng thái mắt và miệng, vật thể, góc quay đầu và face embedding.
- Phương pháp xử lý tín hiệu theo thời gian, state machine, weighted scoring và hysteresis.
- Cơ chế theo dõi tính toàn vẹn của phiên thi trong trình duyệt.
- Kiến trúc backend thời gian thực, phân quyền nhiều tổ chức, lưu bằng chứng và sinh báo cáo.
- Phương pháp đánh giá một hệ thống phát hiện sự kiện theo ground truth và phương pháp kiểm thử các thuộc tính phần mềm.

### 1.4.2. Phạm vi thực hiện

Các nội dung thuộc phạm vi đồ án gồm:

- Webcam đơn hướng vào thí sinh, xử lý hình ảnh trên client desktop Python.
- Sử dụng model pretrained: MTCNN, MediaPipe Face Landmarker, YOLOv8n trên COCO và InceptionResnetV1 trong `facenet-pytorch`.
- Phát hiện hai lớp vật thể trong model hiện tại là `cell phone` và `book`.
- Giám sát các sự kiện trình duyệt bằng extension và áp dụng chính sách camera, microphone, chia sẻ màn hình, toàn màn hình, clipboard và phiên bản extension.
- Hai phương thức tham gia của thí sinh: thông tin thủ công hoặc Google OIDC tùy cấu hình kỳ thi.
- Quản trị nhiều tổ chức với các vai trò System Admin, Organization Admin, Exam Manager và assignment `owner/manager/proctor` trên kỳ thi.
- Dashboard thời gian thực, xem evidence, incident review, xuất báo cáo HTML/PDF, tác vụ report nền và chính sách lưu trữ.
- Chạy cục bộ hoặc triển khai backend bằng Docker Compose với PostgreSQL và Redis.

### 1.4.3. Nội dung ngoài phạm vi

Đồ án không đặt mục tiêu xây dựng một lockdown browser hoặc hệ thống remote attestation hoàn chỉnh. Các nội dung sau nằm ngoài phạm vi:

- Bảo đảm tuyệt đối client không bị sửa khi chạy trên thiết bị do thí sinh kiểm soát.
- Quan sát ứng dụng ngoài trình duyệt, điện thoại thứ hai hoặc thiết bị nằm ngoài góc nhìn camera.
- Phát hiện chắc chắn camera ảo, video replay hoặc deepfake bằng anti-spoofing chuyên dụng.
- Nhận dạng giọng nói, phân tích nội dung âm thanh hoặc truyền video liên tục đến giám thị.
- Huấn luyện lại toàn bộ các model nền từ đầu.
- Tự động kết luận hoặc áp dụng kỷ luật đối với thí sinh.
- Khẳng định khả năng triển khai quy mô lớn nhiều vùng địa lý khi chưa có đánh giá tải và hạ tầng tương ứng.

Việc xác định giới hạn này giúp kết quả đồ án được diễn giải đúng: hệ thống cung cấp tín hiệu và bằng chứng hỗ trợ con người, không phải công cụ chứng minh gian lận một cách tuyệt đối.

## 1.5. Định hướng giải pháp

Đồ án áp dụng nguyên tắc xử lý tại biên kết hợp quản lý tập trung. Pipeline CV chạy tại máy thí sinh để giảm truyền dữ liệu hình ảnh và tránh đưa thư viện học sâu vào backend. Browser extension theo dõi các sự kiện nằm trong phạm vi trình duyệt. Backend tiếp nhận telemetry theo lô, kiểm tra schema, tính hoặc đối chiếu lại kết quả, lưu trạng thái và chuyển tiếp cập nhật đến dashboard.

Luồng CV chính được tổ chức như sau:

```text
Webcam
  → Perception Layer
  → Bảy Signal Extractor
  → State machine theo từng tín hiệu
  → Weighted Risk Fusion và hysteresis cấp phiên
  → ViolationEvent, snapshot và báo cáo
```

Luồng trình duyệt và nền tảng được tổ chức như sau:

```text
Mã tham gia
  → Xác thực thí sinh và policy kỳ thi
  → Kiểm tra thiết bị, consent và khởi tạo monitor
  → Browser event/heartbeat qua WebSocket
  → Backend kiểm tra và tính integrity
  → Dashboard, evidence, incident review và báo cáo
```

Hai loại điểm được giữ tách biệt. `risk_score` phản ánh kết quả pipeline CV; `integrity_score` phản ánh sự kiện trình duyệt và trạng thái thiết bị. Việc tách này tránh gộp các hiện tượng khác bản chất thành một giá trị khó giải thích. Khi xem phiên, giám thị có thể đối chiếu timeline của cả hai nguồn và ảnh bằng chứng trước khi đưa ra nhận định.

## 1.6. Phương pháp thực hiện

Quá trình thực hiện đồ án gồm các nhóm công việc sau:

1. **Khảo sát:** nghiên cứu cơ sở lý thuyết, sản phẩm và dự án liên quan; xác định hạn chế và yêu cầu của hệ thống.
2. **Thiết kế:** xây dựng kiến trúc phân tầng, data contract, state machine, use case, mô hình phân quyền, mô hình dữ liệu và luồng truyền thời gian thực.
3. **Cài đặt:** phát triển desktop CV, extension, backend, dashboard, reporting và các tác vụ vận hành.
4. **Kiểm thử:** viết unit test, integration test, smoke test model, kiểm thử API/WebSocket, cô lập tổ chức, báo cáo và luồng mô phỏng đầu-cuối.
5. **Thực nghiệm:** đánh giá pipeline trên bộ 25 video được gán ground truth trong môi trường thực nghiệm riêng; so sánh với baseline và tổng hợp Precision, Recall, F1-score cùng độ trễ phát hiện.
6. **Phân tích:** đối chiếu kết quả với mục tiêu, chỉ ra giới hạn và đề xuất hướng cải tiến.

Mã nguồn và bộ kiểm thử phần mềm được lưu trong repository của đồ án. Bộ video, ground truth, model/artifact thực nghiệm và biểu đồ đánh giá được tạo trong một môi trường khác do dung lượng và điều kiện chạy, vì vậy Chương 6 ghi rõ nguồn số liệu và phương pháp tính thay vì coi chúng là artifact có sẵn trong repository này.

## 1.7. Các đóng góp chính

Các đóng góp nổi bật của đồ án gồm:

1. Kiến trúc pipeline dùng chung kết quả nhận thức, giúp bảy tín hiệu không chạy lặp detector và có hợp đồng dữ liệu thống nhất.
2. Head pose bằng PnP, identity verification định kỳ và cơ chế enrollment có liveness chớp mắt cơ bản.
3. Cơ chế kết hợp hai cấp: state machine độc lập theo cửa sổ thời gian cho từng tín hiệu và Risk Fusion Engine có trọng số/hysteresis ở cấp phiên.
4. Khả năng giải thích quyết định thông qua trạng thái, tín hiệu đóng góp, mức nghiêm trọng, timeline và snapshot.
5. Kết hợp client CV, browser extension và nền tảng quản lý thời gian thực mà không truyền video liên tục lên backend.
6. Phân quyền nhiều tổ chức theo capability và phạm vi tài nguyên, kèm quyền đọc evidence ngoại lệ có phê duyệt và thời hạn.
7. Mô hình dữ liệu lai SQL–JSONL, incident review tách khỏi sự kiện máy, report job nền và retention có audit.
8. Bộ kiểm thử phần mềm đa tầng và đánh giá định lượng trên bộ video có ground truth.

Chi tiết về vấn đề, giải pháp và kết quả của từng đóng góp được trình bày tại Chương 4.

## 1.8. Bố cục báo cáo

Báo cáo được tổ chức thành bảy chương:

- **Chương 1 – Giới thiệu đề tài:** trình bày bối cảnh, bài toán, mục tiêu, phạm vi, phương pháp và đóng góp dự kiến của đồ án.
- **Chương 2 – Cơ sở lý thuyết:** trình bày nền tảng về xử lý ảnh, phát hiện khuôn mặt, landmark, EAR/MAR, PnP, face embedding, phát hiện vật thể, state machine, hysteresis và các khái niệm nền tảng liên quan đến hệ thống.
- **Chương 3 – Khảo sát và phân tích yêu cầu:** khảo sát giải pháp liên quan, xác định tác nhân, yêu cầu chức năng, yêu cầu phi chức năng, ràng buộc và tiêu chí nghiệm thu.
- **Chương 4 – Các giải pháp và đóng góp nổi bật:** phân tích từng bài toán kỹ thuật, giải pháp được thiết kế và kết quả đạt được ở cấp hệ thống.
- **Chương 5 – Cài đặt hệ thống:** mô tả cấu trúc mã nguồn và cách hiện thực desktop CV, browser extension, backend, dashboard, dữ liệu, bảo mật và triển khai.
- **Chương 6 – Kiểm thử và đánh giá:** trình bày kiểm thử phần mềm, thiết kế thực nghiệm 25 video, baseline, các chỉ số định lượng và phân tích kết quả.
- **Chương 7 – Kết luận và hướng phát triển:** tổng hợp kết quả, giới hạn và các hướng hoàn thiện hệ thống.

## 1.9. Kết chương

Chương 1 đã xác định bài toán của đồ án là xây dựng một hệ thống hỗ trợ giám sát thi có khả năng kết hợp nhiều nguồn tín hiệu, giảm cảnh báo tức thời thiếu ngữ cảnh, cung cấp dữ liệu có thể truy vết và quản lý an toàn trong môi trường nhiều tổ chức. Chương cũng làm rõ mục tiêu, phạm vi và giới hạn để tránh diễn giải hệ thống như một công cụ tự động kết luận gian lận hoặc một lockdown browser hoàn chỉnh.

Chương 2 tiếp theo trình bày các cơ sở lý thuyết làm nền tảng cho pipeline thị giác máy tính, xử lý theo thời gian, xác thực danh tính và kiến trúc truyền/lưu dữ liệu của hệ thống.
