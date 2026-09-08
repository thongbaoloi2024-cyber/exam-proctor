# Chương 1. Giới thiệu đề tài

## 1.1. Đặt vấn đề

Thi trực tuyến ngày càng được sử dụng trong giáo dục, tuyển dụng và các chương trình cấp chứng chỉ. Hình thức này giúp giảm chi phí tổ chức, mở rộng phạm vi tiếp cận và tạo điều kiện cho người học tham gia từ nhiều địa điểm. Tuy nhiên, khi thí sinh làm bài trên thiết bị cá nhân và ngoài không gian thi truyền thống, đơn vị tổ chức khó duy trì mức độ giám sát tương đương một phòng thi trực tiếp.

Các hành vi cần được quan tâm không chỉ gồm những vi phạm rõ ràng như rời khỏi vị trí, xuất hiện người thứ hai hoặc sử dụng điện thoại, mà còn gồm các tình huống khó quan sát hơn: thường xuyên nhìn ra ngoài màn hình, trao đổi với người khác, thay người giữa kỳ thi, chuyển tab, thoát chế độ toàn màn hình, sử dụng clipboard hoặc vô hiệu hóa thiết bị giám sát. Một giám thị theo dõi đồng thời nhiều thí sinh khó quan sát liên tục toàn bộ các dấu hiệu này. Sau kỳ thi, việc chỉ dựa vào trí nhớ của giám thị cũng không cung cấp đủ dữ liệu để xem xét một sự cố theo cách nhất quán.

Giám sát tự động có thể hỗ trợ bằng cách thu thập tín hiệu, đánh dấu những khoảng thời gian bất thường và cung cấp bằng chứng để con người xem xét. Tuy nhiên, đây không phải là bài toán phân loại ảnh đơn lẻ. Dữ liệu webcam chịu ảnh hưởng của ánh sáng, góc đặt camera, đặc điểm khuôn mặt, kính, hiện tượng che khuất và năng lực phần cứng. Một lần chớp mắt hoặc quay đầu trong thời gian ngắn không đồng nghĩa với gian lận. Tương tự, việc cửa sổ thi mất trạng thái tập trung có thể bắt nguồn từ thông báo hệ thống thay vì hành vi cố ý. Nếu mọi quan sát tức thời đều tạo cảnh báo, số lượng cảnh báo sai sẽ làm giảm giá trị của hệ thống và có thể gây bất lợi cho thí sinh.

Bài toán còn đặt ra các yêu cầu về vận hành. Một giải pháp có khả năng triển khai cần quản lý tổ chức, kỳ thi, giám thị và phiên thi; truyền trạng thái theo thời gian thực; kiểm soát quyền truy cập dữ liệu nhạy cảm; lưu trữ ảnh và sự kiện có thể truy vết; đồng thời tạo báo cáo sau kỳ thi. Truyền video liên tục đến máy chủ làm tăng nhu cầu băng thông và phạm vi xử lý dữ liệu cá nhân, trong khi một ứng dụng hoàn toàn cục bộ không đáp ứng nhu cầu giám sát tập trung. Vì vậy, hệ thống cần cân bằng giữa xử lý tại thiết bị, quản lý tập trung, khả năng giải thích và bảo vệ quyền riêng tư.

Từ các vấn đề trên, đồ án lựa chọn đề tài **“Hệ thống giám sát thi trực tuyến bằng thị giác máy tính”**. Hệ thống kết hợp bảy tín hiệu thị giác máy tính, các sự kiện toàn vẹn trình duyệt và một nền tảng quản lý nhiều tổ chức. Mục tiêu của hệ thống là hỗ trợ giám thị phát hiện và xem xét sự kiện đáng ngờ, không tự động kết luận thí sinh gian lận. Quyết định cuối cùng vẫn thuộc về người có thẩm quyền dựa trên quy chế thi, ngữ cảnh và bằng chứng liên quan.

## 1.2. Động lực và khoảng trống cần giải quyết

Các giải pháp giám sát thi hiện có có thể được chia thành hai nhóm. Nhóm sản phẩm thương mại thường cung cấp nhiều chức năng như kiểm tra thiết bị, khóa hoặc theo dõi trình duyệt, ghi hình và hỗ trợ giám thị. Ưu điểm của nhóm này là quy trình vận hành tương đối hoàn chỉnh. Tuy nhiên, thuật toán phát hiện thường không được công bố đầy đủ; khả năng điều chỉnh, kiểm chứng độc lập và triển khai theo yêu cầu riêng có thể bị hạn chế.

Nhóm dự án mã nguồn mở và nghiên cứu học thuật tạo điều kiện khảo sát thuật toán và tái sử dụng mã nguồn. Một số dự án kết hợp OpenCV, MediaPipe, MTCNN và YOLO để nhận biết khuôn mặt, trạng thái mắt, chuyển động miệng hoặc vật thể. Tuy vậy, nhiều giải pháp dừng ở một chương trình cục bộ, xử lý từng điều kiện bằng chuỗi `if-elif` và ghi một nhãn cho mỗi khung hình. Cách làm này có bốn hạn chế chính:

1. Kết quả của một khung hình dễ bị ảnh hưởng bởi nhiễu và không biểu diễn được thời lượng hành vi.
2. Nhiều tín hiệu xảy ra đồng thời không được kết hợp theo mức độ quan trọng.
3. Một số phép đo dựa trên độ lệch điểm ảnh hoặc khoảng cách tuyệt đối phụ thuộc vào độ phân giải, tốc độ khung hình và vị trí khuôn mặt.
4. Ứng dụng thiếu lớp quản lý kỳ thi, phân quyền, theo dõi thời gian thực, lưu bằng chứng và đánh giá sau sự kiện.

Đồ án tiếp cận khoảng trống trên ở cấp hệ thống thay vì chỉ ghép nối các mô hình nhận diện. Các mô hình được huấn luyện trước đóng vai trò thành phần nền. Phần thiết kế của đồ án tập trung vào chuỗi xử lý dùng chung, hợp đồng dữ liệu, xử lý theo thời gian, tổng hợp rủi ro, xác thực lại danh tính trong phiên, tích hợp trình duyệt, phân quyền theo tài nguyên và vòng đời quản lý bằng chứng.

## 1.3. Mục tiêu của đề tài

### 1.3.1. Mục tiêu tổng quát

Xây dựng một hệ thống giám sát thi trực tuyến có khả năng thu thập và tổng hợp nhiều tín hiệu bất thường, hỗ trợ giám thị theo dõi phiên thi theo thời gian thực và xem lại bằng chứng sau kỳ thi; đồng thời bảo đảm hệ thống có cấu trúc mô-đun, có thể kiểm thử, cấu hình và mở rộng.

### 1.3.2. Mục tiêu cụ thể

Để đạt mục tiêu tổng quát, đồ án xác định các mục tiêu cụ thể sau:

- Xây dựng tầng nhận thức dùng chung để phát hiện khuôn mặt, trích xuất điểm mốc và phát hiện vật thể mà không chạy lặp cùng một mô hình cho từng tín hiệu.
- Cài đặt bảy tín hiệu gồm `FACE_PRESENCE`, `MULTI_FACE`, `EYE_STATE`, `MOUTH_STATE`, `OBJECT_PRESENCE`, `HEAD_POSE` và `IDENTITY` theo một giao diện lập trình thống nhất.
- Ước lượng ba góc quay đầu yaw, pitch và roll bằng bài toán Perspective-n-Point (PnP), thay cho phép so sánh độ lệch điểm ảnh đơn giản.
- Đăng ký và kiểm tra lại danh tính bằng véc-tơ đặc trưng khuôn mặt trong suốt phiên thi; kết hợp thử thách chớp mắt cơ bản ở bước đăng ký khuôn mặt.
- Xây dựng máy trạng thái theo cửa sổ thời gian cho từng tín hiệu và bộ tổng hợp rủi ro có trọng số, vùng trễ hai cấp và khả năng giải thích mức đóng góp của tín hiệu.
- Xây dựng tiện ích mở rộng trình duyệt để theo dõi trạng thái tập trung, chuyển thẻ, chế độ toàn màn hình, bảng tạm, camera, microphone và chia sẻ màn hình theo chính sách kỳ thi.
- Xây dựng dịch vụ FastAPI và bảng điều khiển để quản lý tổ chức, thành viên, kỳ thi, phiên thi, sự cố và báo cáo; truyền cập nhật bằng WebSocket.
- Thiết kế phân quyền theo vai trò, tổ chức và nhiệm vụ được giao trong từng kỳ thi; giới hạn quyền truy cập bằng chứng nhạy cảm và ghi nhật ký hoạt động.
- Kết hợp cơ sở dữ liệu quan hệ với JSONL và ảnh chụp bằng chứng để vừa truy vấn nhanh trạng thái mới nhất, vừa tái dựng diễn biến theo thời gian.
- Đánh giá giải pháp bằng kiểm thử phần mềm, kiểm thử tích hợp và số liệu tổng hợp từ thực nghiệm 25 video có nhãn tham chiếu được thực hiện trong một môi trường riêng.

## 1.4. Đối tượng và phạm vi nghiên cứu

### 1.4.1. Đối tượng nghiên cứu

Đối tượng nghiên cứu của đồ án gồm:

- Các kỹ thuật phát hiện khuôn mặt, điểm mốc khuôn mặt, trạng thái mắt và miệng, vật thể, góc quay đầu và véc-tơ đặc trưng khuôn mặt.
- Phương pháp xử lý tín hiệu theo thời gian, máy trạng thái, tổng hợp có trọng số và vùng trễ.
- Cơ chế theo dõi tính toàn vẹn của phiên thi trong trình duyệt.
- Kiến trúc dịch vụ thời gian thực, phân quyền nhiều tổ chức, lưu bằng chứng và sinh báo cáo.
- Phương pháp đánh giá hệ thống phát hiện sự kiện theo nhãn tham chiếu và phương pháp kiểm thử các thuộc tính phần mềm.

### 1.4.2. Phạm vi thực hiện

Các nội dung thuộc phạm vi đồ án gồm:

- Webcam hướng về phía thí sinh; hình ảnh được xử lý trên ứng dụng máy tính để bàn viết bằng Python.
- Sử dụng các mô hình được huấn luyện trước gồm MTCNN, MediaPipe Face Landmarker, YOLOv8n trên COCO và InceptionResnetV1 trong `facenet-pytorch`.
- Phát hiện hai lớp vật thể của mô hình hiện tại là `cell phone` và `book`.
- Giám sát các sự kiện trình duyệt bằng tiện ích mở rộng; áp dụng chính sách đối với camera, microphone, chia sẻ màn hình, chế độ toàn màn hình, bảng tạm và phiên bản tiện ích.
- Hai phương thức tham gia của thí sinh: thông tin thủ công hoặc Google OIDC tùy cấu hình kỳ thi.
- Quản trị nhiều tổ chức với các vai trò System Admin, Organization Admin, Exam Manager và các nhiệm vụ `owner/manager/proctor` trên kỳ thi.
- Bảng điều khiển thời gian thực, xem bằng chứng, hậu kiểm sự cố, xuất báo cáo HTML/PDF, xử lý báo cáo nền và áp dụng chính sách lưu trữ.
- Chạy cục bộ hoặc triển khai dịch vụ phía máy chủ bằng Docker Compose với PostgreSQL và Redis.

### 1.4.3. Nội dung ngoài phạm vi

Đồ án không đặt mục tiêu xây dựng một lockdown browser hoặc hệ thống remote attestation hoàn chỉnh. Các nội dung sau nằm ngoài phạm vi:

- Bảo đảm tuyệt đối client không bị sửa khi chạy trên thiết bị do thí sinh kiểm soát.
- Quan sát ứng dụng ngoài trình duyệt, điện thoại thứ hai hoặc thiết bị nằm ngoài góc nhìn camera.
- Phát hiện chắc chắn camera ảo, video replay hoặc deepfake bằng anti-spoofing chuyên dụng.
- Nhận dạng giọng nói, phân tích nội dung âm thanh hoặc truyền video liên tục đến giám thị.
- Huấn luyện lại toàn bộ các mô hình nền từ đầu.
- Tự động kết luận hoặc áp dụng kỷ luật đối với thí sinh.
- Khẳng định khả năng triển khai quy mô lớn nhiều vùng địa lý khi chưa có đánh giá tải và hạ tầng tương ứng.

Việc xác định giới hạn này giúp kết quả đồ án được diễn giải đúng: hệ thống cung cấp tín hiệu và bằng chứng hỗ trợ con người, không phải công cụ chứng minh gian lận một cách tuyệt đối.

## 1.5. Định hướng giải pháp

Đồ án áp dụng nguyên tắc xử lý tại biên kết hợp với quản lý tập trung. Chuỗi xử lý thị giác máy tính chạy trên máy thí sinh để hạn chế truyền dữ liệu hình ảnh và tách các thư viện học sâu khỏi dịch vụ phía máy chủ. Tiện ích mở rộng theo dõi những sự kiện nằm trong phạm vi trình duyệt. Dịch vụ phía máy chủ tiếp nhận dữ liệu giám sát theo lô, kiểm tra lược đồ, tính lại hoặc đối chiếu kết quả, lưu trạng thái và chuyển tiếp cập nhật đến bảng điều khiển.

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
  → Xác thực thí sinh và tải chính sách kỳ thi
  → Kiểm tra thiết bị, ghi nhận sự đồng ý và khởi tạo giám sát
  → Sự kiện trình duyệt và nhịp kết nối qua WebSocket
  → Máy chủ kiểm tra và tính điểm toàn vẹn
  → Bảng điều khiển, bằng chứng, hậu kiểm sự cố và báo cáo
```

Hai loại điểm được tách biệt. `risk_score` phản ánh kết quả xử lý thị giác máy tính, còn `integrity_score` phản ánh sự kiện trình duyệt và trạng thái thiết bị. Cách tổ chức này tránh gộp các hiện tượng khác bản chất thành một giá trị khó giải thích. Khi xem lại phiên thi, giám thị có thể đối chiếu diễn biến theo thời gian của cả hai nguồn với ảnh bằng chứng trước khi đưa ra nhận định.

## 1.6. Phương pháp thực hiện

Quá trình thực hiện đồ án gồm các nhóm công việc sau:

1. **Khảo sát:** nghiên cứu cơ sở lý thuyết, sản phẩm và dự án liên quan; xác định hạn chế và yêu cầu của hệ thống.
2. **Thiết kế:** xây dựng kiến trúc phân tầng, hợp đồng dữ liệu, máy trạng thái, ca sử dụng, mô hình phân quyền, mô hình dữ liệu và luồng truyền thời gian thực.
3. **Cài đặt:** phát triển ứng dụng thị giác máy tính, tiện ích mở rộng, dịch vụ phía máy chủ, bảng điều khiển, thành phần tạo báo cáo và các tác vụ vận hành.
4. **Kiểm thử:** xây dựng kiểm thử đơn vị, kiểm thử tích hợp, kiểm thử khởi tạo mô hình, kiểm thử API/WebSocket, cô lập tổ chức, báo cáo và luồng mô phỏng đầu-cuối.
5. **Thực nghiệm:** phân tích số liệu tổng hợp của bộ 25 video được gán nhãn tham chiếu trong môi trường thực nghiệm riêng; so sánh với phương pháp cơ sở và tính các chỉ số Precision, Recall, F1-score cùng độ trễ phát hiện.
6. **Phân tích:** đối chiếu kết quả với mục tiêu, chỉ ra giới hạn và đề xuất hướng cải tiến.

Mã nguồn và bộ kiểm thử phần mềm được lưu trong kho mã nguồn của đồ án. Bộ video, nhãn tham chiếu, mô hình và các tệp kết quả thực nghiệm được tạo trong một môi trường khác nhưng chưa được đưa vào bản bàn giao hiện tại. Vì vậy, Chương 6 phân biệt rõ kết quả có thể chạy lại từ kho mã nguồn với số liệu chỉ được ghi nhận từ môi trường thực nghiệm; số liệu thuộc nhóm thứ hai chưa thể được kiểm chứng độc lập từ bản bàn giao này.

## 1.7. Các đóng góp chính

Các đóng góp nổi bật của đồ án gồm:

1. Kiến trúc xử lý dùng chung kết quả nhận thức, giúp bảy tín hiệu không chạy lặp bộ phát hiện và sử dụng một hợp đồng dữ liệu thống nhất.
2. Ước lượng góc quay đầu bằng PnP, kiểm tra lại danh tính định kỳ và đăng ký khuôn mặt có thử thách chớp mắt cơ bản.
3. Cơ chế kết hợp hai cấp: máy trạng thái độc lập theo cửa sổ thời gian cho từng tín hiệu và bộ tổng hợp rủi ro có trọng số, vùng trễ ở cấp phiên.
4. Khả năng giải thích quyết định thông qua trạng thái, tín hiệu đóng góp, mức nghiêm trọng, diễn biến theo thời gian và ảnh chụp bằng chứng.
5. Kết hợp ứng dụng thị giác máy tính, tiện ích mở rộng trình duyệt và nền tảng quản lý thời gian thực mà không truyền video liên tục đến máy chủ.
6. Phân quyền nhiều tổ chức theo năng lực và phạm vi tài nguyên, kèm cơ chế cấp quyền đọc bằng chứng ngoại lệ có phê duyệt và thời hạn.
7. Mô hình dữ liệu lai SQL–JSONL, kết quả hậu kiểm tách khỏi sự kiện máy, tác vụ tạo báo cáo chạy nền và chính sách lưu trữ có nhật ký kiểm toán.
8. Bộ kiểm thử phần mềm nhiều tầng và phần phân tích định lượng trên bộ video có nhãn tham chiếu, kèm công bố giới hạn tái lập.

Chi tiết về vấn đề, giải pháp và kết quả của từng đóng góp được trình bày tại Chương 4.

## 1.8. Bố cục báo cáo

Báo cáo được tổ chức thành bảy chương:

- **Chương 1 – Giới thiệu đề tài:** trình bày bối cảnh, bài toán, mục tiêu, phạm vi, phương pháp và đóng góp dự kiến của đồ án.
- **Chương 2 – Cơ sở lý thuyết:** trình bày nền tảng về xử lý ảnh, phát hiện khuôn mặt, điểm mốc, EAR/MOR, PnP, véc-tơ đặc trưng khuôn mặt, phát hiện vật thể, máy trạng thái, vùng trễ và các khái niệm liên quan đến hệ thống.
- **Chương 3 – Khảo sát và phân tích yêu cầu:** khảo sát giải pháp liên quan, xác định tác nhân, yêu cầu chức năng, yêu cầu phi chức năng, ràng buộc và tiêu chí nghiệm thu.
- **Chương 4 – Thiết kế giải pháp và các đóng góp:** phân tích từng bài toán kỹ thuật, giải pháp được thiết kế và kết quả đạt được ở cấp hệ thống.
- **Chương 5 – Cài đặt hệ thống:** mô tả cấu trúc mã nguồn và cách hiện thực ứng dụng CV, tiện ích mở rộng trình duyệt, dịch vụ phía máy chủ, bảng điều khiển, dữ liệu, bảo mật và triển khai.
- **Chương 6 – Kiểm thử và đánh giá:** trình bày kiểm thử phần mềm, thiết kế thực nghiệm 25 video, phương pháp cơ sở, các chỉ số định lượng và phân tích kết quả.
- **Chương 7 – Kết luận và hướng phát triển:** tổng hợp kết quả, giới hạn và các hướng hoàn thiện hệ thống.

## 1.9. Kết chương

Chương 1 đã xác định bài toán của đồ án là xây dựng một hệ thống hỗ trợ giám sát thi có khả năng kết hợp nhiều nguồn tín hiệu, giảm cảnh báo tức thời thiếu ngữ cảnh, cung cấp dữ liệu có thể truy vết và quản lý an toàn trong môi trường nhiều tổ chức. Chương cũng làm rõ mục tiêu, phạm vi và giới hạn để tránh diễn giải hệ thống như một công cụ tự động kết luận gian lận hoặc một lockdown browser hoàn chỉnh.

Chương 2 tiếp theo trình bày các cơ sở lý thuyết làm nền tảng cho pipeline thị giác máy tính, xử lý theo thời gian, xác thực danh tính và kiến trúc truyền/lưu dữ liệu của hệ thống.
