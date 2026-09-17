# Chương 7. Kết luận và hướng phát triển

## 7.1. Tổng kết đề tài

Đồ án đã xây dựng một hệ thống hỗ trợ giám sát thi gồm chuỗi xử lý thị giác máy tính tại máy thí sinh, tiện ích mở rộng trình duyệt và nền tảng FastAPI với bảng điều khiển. Từ mục tiêu ban đầu là một ứng dụng webcam cục bộ, phạm vi được mở rộng sang quản lý nhiều tổ chức, phân quyền theo kỳ thi, truyền dữ liệu thời gian thực, quản lý bằng chứng, hậu kiểm sự cố và tạo báo cáo.

Hệ thống không tự động kết luận thí sinh gian lận. Đầu ra của mô hình và tiện ích mở rộng được biểu diễn thành tín hiệu, trạng thái, điểm số, sự kiện và ảnh bằng chứng để giám thị xem xét theo quy chế và bối cảnh của kỳ thi.

## 7.2. Kết quả chính đạt được

### 7.2.1. Chuỗi xử lý thị giác máy tính có cấu trúc

Đồ án đã triển khai tầng nhận thức dùng chung gồm MTCNN, MediaPipe Face Landmarker và YOLOv8n. Kết quả được đóng gói vào `PerceptionResult` và chia sẻ cho bảy bộ trích xuất tín hiệu:

- Hiện diện khuôn mặt.
- Nhiều khuôn mặt.
- Trạng thái mắt.
- Trạng thái miệng.
- Hiện diện vật thể.
- Tư thế đầu.
- Danh tính.

Mỗi tín hiệu tuân theo một giao diện chung và chỉ chịu trách nhiệm cho hiện tượng tương ứng. Tình trạng thiếu khuôn mặt không bị diễn giải đồng thời thành mắt nhắm, góc quay đầu bất thường và sai khác danh tính. Khi một bộ phát hiện gặp lỗi tạm thời, cơ chế dự phòng giúp chuỗi xử lý không kết thúc đột ngột.

### 7.2.2. Hai cải tiến kỹ thuật so với phương pháp cơ sở

Ước lượng góc quay đầu sử dụng các cặp tương ứng giữa điểm mốc 2D và mô hình mặt 3D, kết hợp `solvePnP` để tính góc quay ngang, góc quay dọc và góc nghiêng. Cách này tạo đại lượng góc có ý nghĩa hình học thay cho độ lệch điểm ảnh phụ thuộc vào độ phân giải.

Tín hiệu danh tính sử dụng InceptionResnetV1 để tạo véc-tơ đặc trưng 512 chiều, lấy trung bình từ nhiều khung hình đăng ký và so sánh độ tương đồng cosin theo chu kỳ. Vùng cảnh báo, ngưỡng không khớp và yêu cầu nhiều kết quả liên tiếp giúp tránh đánh giá từ một quan sát đơn lẻ. Bước đăng ký còn được ràng buộc với thử thách chớp mắt cơ bản.

### 7.2.3. Bộ tổng hợp rủi ro có trạng thái và khả năng giải thích

Mỗi tín hiệu có máy trạng thái `NORMAL → SUSPICIOUS → ALERT` dựa trên cửa sổ thời gian và vùng trễ riêng. Tầng phiên kết hợp trạng thái bằng tổng có trọng số và vùng trễ hai ngưỡng. Sự kiện vi phạm chỉ được sinh tại cạnh chuyển vào cảnh báo, tránh tạo một bản ghi cho mọi khung hình.

Sự kiện lưu điểm rủi ro, mức nghiêm trọng, loại vi phạm chính và các tín hiệu đóng góp. Diễn biến chuyển trạng thái và điểm rủi ro được lưu riêng, giúp báo cáo giải thích nguyên nhân cảnh báo thay vì chỉ đưa ra nhãn cuối.

### 7.2.4. Giám sát trình duyệt và nền tảng thời gian thực

Tiện ích mở rộng đã triển khai luồng nhập mã, xác thực thủ công hoặc qua Google, ghi nhận sự đồng ý, kiểm tra chính sách và giám sát nội dung. Tiện ích theo dõi trạng thái tập trung/chuyển thẻ, toàn màn hình, bảng tạm, camera, micrô, chia sẻ màn hình và nhịp kết nối. Điểm toàn vẹn trình duyệt được tính tách biệt với điểm rủi ro thị giác máy tính.

Dịch vụ FastAPI hỗ trợ:

- Quản lý tổ chức, thành viên, lời mời và chính sách.
- Quản lý vòng đời kỳ thi, mã tham gia, nhiệm vụ được giao và trạng thái sẵn sàng.
- Xác thực nhân sự/thí sinh, MFA và Google OIDC.
- WebSocket cho máy khách và bảng điều khiển với vé kết nối dùng một lần.
- Bảng điều khiển thời gian thực và trang chi tiết phiên.
- Bằng chứng, hậu kiểm sự cố, tác vụ báo cáo và chính sách lưu trữ.
- Docker Compose với PostgreSQL, Redis, dịch vụ FastAPI và tiến trình báo cáo.

### 7.2.5. Phân quyền và bảo vệ dữ liệu

Quyền được xác định từ vai trò hệ thống, tư cách thành viên tổ chức và nhiệm vụ trong kỳ thi. Quản trị viên hệ thống không mặc nhiên được xem dữ liệu thí sinh; quyền ngoại lệ phải được phê duyệt, chỉ cho phép đọc và có thời hạn. Máy chủ kiểm tra phạm vi tổ chức và tài nguyên đối với REST, WebSocket và thao tác tải tệp.

Máy khách được coi là nguồn không hoàn toàn tin cậy. Máy chủ kiểm tra lược đồ, dấu thời gian, sự hiện diện của đủ bảy tín hiệu, điểm rủi ro, trạng thái, mức nghiêm trọng, mức đóng góp, sự kiện trình duyệt và ảnh tải lên. Dữ liệu giao diện được dựng bằng API DOM an toàn; tiêu đề bảo mật và nhật ký kiểm toán được áp dụng cho các luồng nhạy cảm.

### 7.2.6. Dữ liệu và báo cáo

Đồ án kết hợp SQL cho siêu dữ liệu và trạng thái hiện tại với JSONL cho chuỗi sự kiện. Ảnh chụp được lưu bằng tên do máy chủ sinh. Kết quả hậu kiểm được tách khỏi sự kiện vi phạm gốc để nhận định của con người không làm thay đổi dữ liệu máy. Chuỗi xử lý báo cáo có thể sinh HTML/PDF khi thiếu một phần dữ liệu; tác vụ báo cáo chạy trong tiến trình nền.

## 7.3. Kết quả kiểm thử và thực nghiệm

Kết quả kiểm thử phần mềm và thực nghiệm cần được diễn giải riêng. Bộ kiểm thử tiện ích mở rộng được chạy lại đạt 8/8 ca. Đối với Python, kết quả chạy toàn bộ bộ kiểm thử và kết quả chạy lại ca lỗi được trình bày chi tiết tại mục 6.2; kết quả cho thấy một ca có dấu hiệu phụ thuộc thứ tự hoặc không ổn định, vì ca đó đạt khi chạy riêng. Do đó, báo cáo không dùng số lượng ca kiểm thử như bằng chứng về độ chính xác nhận diện.

- Phép đo hiệu năng tổng hợp trên CPU đạt khoảng 25,3 FPS; MTCNN là nút thắt lớn nhất.

Theo bảng tổng hợp của cấu hình thực nghiệm bên ngoài gồm 25 video và 199.470 khung hình:

| Chỉ số | Kết quả |
|---|---:|
| Độ chính xác (Precision) | 0,7083 |
| Độ bao phủ (Recall) | 0,8500 |
| F1-score | 0,7727 |
| Accuracy | 0,9248 |
| Specificity | 0,9380 |
| FPR | 0,0620 |

So với phương pháp cơ sở được báo cáo, độ chính xác tăng 0,0562, độ bao phủ tăng 0,1270 và điểm F1 tăng 0,0876 theo giá trị tuyệt đối. Các giá trị vượt những ngưỡng mục tiêu nêu trong tài liệu thực nghiệm; tuy nhiên, thời điểm xác lập mục tiêu và tệp dự đoán gốc chưa có trong bản bàn giao để kiểm tra độc lập.

Kết quả không được diễn giải thành độ chính xác phổ quát. Bộ dữ liệu và tệp thực nghiệm nằm ngoài kho mã nguồn; cấu hình tạo số liệu khác một phần so với cấu hình hiện tại; số người, thiết bị và điều kiện quay còn hạn chế.

## 7.4. Những hạn chế còn tồn tại

### 7.4.1. Ứng dụng thị giác máy tính và tiện ích mở rộng chưa hợp nhất hoàn toàn

Ứng dụng thị giác máy tính và tiện ích mở rộng đều có thể tạo hoặc gửi dữ liệu, nhưng chưa có cầu nối nhắn tin với ứng dụng cục bộ (native messaging) để phối hợp như một máy khách thống nhất trong cùng phiên trình duyệt. Việc hợp nhất cần giải quyết quyền quản lý mã xác thực phiên, đồng bộ vòng đời, thử lại khi lỗi và chống sự kiện trùng.

### 7.4.2. Đồng bộ khi mất mạng chưa đầy đủ

Ứng dụng thị giác máy tính vẫn ghi nhật ký và sinh báo cáo cục bộ khi mất kết nối với máy chủ. Tuy nhiên, dữ liệu phát sinh trong thời gian ngoại tuyến chưa được đồng bộ bù đầy đủ. Tiện ích mở rộng có hàng đợi kết nối lại nhưng dung lượng và vòng đời lưu trữ vẫn bị giới hạn bởi trình duyệt.

### 7.4.3. Giới hạn của mô hình thị giác máy tính

- MTCNN và các điểm mốc chịu ảnh hưởng của ánh sáng, góc lớn và che khuất.
- EAR có thể sai khi cả hai mắt cùng bị biến dạng phối cảnh.
- Tín hiệu tư thế đầu không phân biệt chắc chắn quay đầu tự nhiên với nhìn tài liệu.
- YOLOv8n có thể bỏ sót điện thoại nhỏ/mặt lưng hoặc nhận nhầm vật thể.
- Véc-tơ đặc trưng khuôn mặt nhạy với góc, ánh sáng và chất lượng đăng ký.
- Thử thách chớp mắt không chống được kỹ thuật phát lại video hoặc giả mạo chuyên dụng.

### 7.4.4. Giới hạn của tiện ích mở rộng trình duyệt

Tiện ích chỉ quan sát dữ liệu mà WebExtensions API cho phép. Thành phần này không quan sát được ứng dụng cục bộ khác, máy ảo, điều khiển máy tính từ xa hoặc điện thoại thứ hai. Nếu tiện ích không được ký và cài đặt bắt buộc trong trình duyệt được quản lý, người có toàn quyền trên thiết bị vẫn có thể vô hiệu hóa hoặc sửa đổi máy khách.

### 7.4.5. Giới hạn về quy mô và vận hành

Redis đã hỗ trợ quyền giữ kết nối của máy khách và phát–nhận cập nhật bảng điều khiển khi được cấu hình, nhưng triển khai quy mô lớn vẫn cần:

- Kho lưu trữ đối tượng thay cho hệ thống tệp cục bộ dùng chung.
- Hàng đợi công việc và cơ chế thử lại có khả năng quan sát tốt hơn.
- Sao lưu/khôi phục và phục hồi sau thảm họa.
- Chỉ số, theo vết, nhật ký tập trung và cảnh báo vận hành.
- Kiểm thử tải với nhiều tiến trình nền/nhiều kỳ thi đồng thời.
- Quy trình chuyển đổi lược đồ/khôi phục được chuẩn hóa.

### 7.4.6. Khả năng tái lập thực nghiệm

Kho mã nguồn chưa chứa danh mục dữ liệu, nhãn, kết quả dự đoán, tệp mô hình và thông tin môi trường của bộ 25 video. Vì vậy, ma trận nhầm lẫn và các chỉ số được giữ như kết quả từ môi trường ngoài nhưng chưa thể được tái lập độc lập từ bản bàn giao hiện tại. Đây là giới hạn học thuật cần được ưu tiên khắc phục.

### 7.4.7. Quyền riêng tư và công bằng

Hình ảnh khuôn mặt và dữ liệu hành vi là dữ liệu nhạy cảm. Một triển khai thực tế cần thông báo minh bạch, ghi nhận sự đồng ý phù hợp, xác định thời hạn lưu trữ, quy trình khiếu nại, quyền truy cập bằng chứng và đánh giá sai lệch giữa các nhóm người dùng. Bộ dữ liệu nhỏ hiện tại chưa đủ để kết luận về tính công bằng giữa màu da, người đeo kính, đặc điểm khuôn mặt, camera và điều kiện ánh sáng.

## 7.5. Hướng phát triển

### 7.5.1. Ưu tiên 1 – Đóng gói thực nghiệm có thể tái lập

Đây là công việc ưu tiên cao nhất để củng cố kết luận khoa học:

- Lưu danh mục video và hàm băm của từng tệp.
- Lưu nhãn tham chiếu theo khoảng thời gian và loại vi phạm.
- Công bố cách chia tập huấn luyện/xác thực/kiểm thử theo video và người tham gia.
- Lưu mã phiên bản, cấu hình, tệp mô hình và tệp khóa phiên bản thư viện phụ thuộc.
- Lưu dự đoán JSONL và kịch bản tính chỉ số, biểu đồ.
- Báo cáo mức đồng thuận giữa người gán nhãn và kết quả theo từng tín hiệu.

Khi có đủ tệp thực nghiệm, cần chạy lại cả cấu hình đã tạo số liệu và cấu hình hiện tại trên cùng một tập kiểm thử.

### 7.5.2. Ưu tiên 2 – Hợp nhất ứng dụng thị giác máy tính với tiện ích mở rộng

Có thể phát triển ứng dụng đồng hành được ký và giao tiếp với tiện ích qua cơ chế nhắn tin với ứng dụng cục bộ. Tiện ích quản lý phiên trình duyệt và chính sách; ứng dụng đồng hành quản lý webcam và mô hình; cả hai dùng cùng mã phiên và số thứ tự thông điệp. Thiết kế cần có xác thực hai chiều, chính sách phiên bản và cơ chế chống phát lại.

### 7.5.3. Ưu tiên 3 – Cải thiện chất lượng nhận diện

- Thu thập dữ liệu đa dạng hơn theo người, camera và ánh sáng.
- Hiệu chuẩn EAR và ngưỡng danh tính trong bước đăng ký theo từng người.
- Kết hợp độ tin cậy của góc quay đầu với trạng thái mắt.
- Đánh giá YOLOv8s hoặc tinh chỉnh mô hình với cách chia tập huấn luyện/kiểm thử rõ ràng.
- Xử lý tín hiệu danh tính bất đồng bộ để tránh làm chậm khung hình.
- Thử nghiệm RetinaFace, ArcFace hoặc mô hình ổn định hơn khi có đủ tài nguyên.
- Tích hợp cơ chế chống giả mạo đã được đánh giá trên video phát lại và nội dung giả mạo.

Mọi cải tiến cần được đánh giá bằng nghiên cứu loại bỏ thành phần, thay vì chỉ thay đổi ngưỡng theo cảm nhận.

### 7.5.4. Ưu tiên 4 – Hoàn thiện sản phẩm và hạ tầng

- Ký và cài đặt bắt buộc tiện ích trong trình duyệt được quản lý.
- Ký ứng dụng đồng hành cục bộ, kiểm tra phiên bản và cập nhật an toàn.
- Dùng HTTPS bắt buộc, trình quản lý thông tin bí mật và cơ chế xoay vòng khóa.
- Chuyển ảnh chụp/báo cáo sang kho lưu trữ đối tượng có URL ký số ngắn hạn.
- Bổ sung trung tâm vận hành, giám sát hàng đợi và cảnh báo lưu trữ/hạn mức.
- Kiểm thử tải với nhiều tổ chức/kỳ thi/tiến trình nền và xây dựng kế hoạch năng lực.
- Chuẩn hóa chuyển đổi lược đồ bằng công cụ hỗ trợ phiên bản/khôi phục.

### 7.5.5. Ưu tiên 5 – Quản trị dữ liệu và trải nghiệm người dùng

- Xây dựng quy trình yêu cầu của chủ thể dữ liệu, xuất/xóa dữ liệu và lưu giữ theo yêu cầu pháp lý.
- Đóng dấu nhận diện trên báo cáo/bằng chứng và thông báo khi có truy cập nhạy cảm.
- Cải thiện bước kiểm tra trước phiên và hướng dẫn khắc phục lỗi.
- Thiết kế cơ chế tiếp tục/tham gia lại an toàn sau khi ứng dụng dừng đột ngột hoặc đổi thiết bị.
- Đánh giá khả năng tiếp cận và hỗ trợ đa ngôn ngữ/múi giờ.
- Xây dựng quy trình khiếu nại để thí sinh có thể phản hồi cảnh báo sai.

## 7.6. Bài học kinh nghiệm

Quá trình thực hiện cho thấy một số bài học có thể tổng quát hóa:

1. Công thức đúng chưa bảo đảm phần cài đặt đúng; sai lệch tỉ lệ của tọa độ chuẩn hóa chỉ được phát hiện khi thử với webcam thật.
2. Ngưỡng theo số khung hình không ổn định khi FPS thay đổi; thời lượng và cửa sổ theo giây phù hợp hơn.
3. Một tín hiệu không nên tự diễn giải lỗi của tầng khác; thiếu điểm mốc cần trả “không đủ dữ liệu”.
4. Cảnh báo cần trạng thái và vùng trễ; nhãn trên từng khung hình tạo quá nhiều nhiễu.
5. Giao diện phía người dùng không phải ranh giới bảo mật; năng lực và phạm vi tổ chức phải được thực thi ở máy chủ.
6. Dữ liệu tổng hợp hữu ích cho kiểm thử tải và báo cáo nhưng không thay thế video thật có nhãn tham chiếu.
7. Chỉ số thực nghiệm chỉ có giá trị khoa học đầy đủ khi đi kèm tệp dữ liệu và quy trình tái lập.

## 7.7. Kết luận

Đồ án đã hiện thực một nền tảng hỗ trợ giám sát thi có cấu trúc, kết hợp bảy tín hiệu thị giác máy tính, máy trạng thái, bộ tổng hợp rủi ro, tiện ích theo dõi trình duyệt, bảng điều khiển thời gian thực, phân quyền nhiều tổ chức và quy trình quản lý bằng chứng, báo cáo. Bộ kiểm thử cung cấp bằng chứng về tính nhất quán của phần cài đặt trong các tình huống đã mô tả, đồng thời lần chạy lại cho thấy cần xử lý một ca kiểm thử Python có dấu hiệu không ổn định. Số liệu từ cấu hình thực nghiệm 25 video ghi nhận độ chính xác 0,7083, độ bao phủ 0,8500 và điểm F1 bằng 0,7727; hướng kết hợp đa tín hiệu có kết quả cao hơn phương pháp cơ sở trong bảng tổng hợp, nhưng chưa thể được tái lập độc lập từ bản bàn giao.

Đóng góp chính không phải là một mô hình mới, mà là cách tổ chức nhiều mô hình và thành phần phần mềm thành chuỗi xử lý có trạng thái, có khả năng giải thích và kiểm soát truy cập. Hệ thống hiện phù hợp với mục đích nghiên cứu, trình diễn và thử nghiệm có kiểm soát. Trước khi sử dụng cho kỳ thi rủi ro cao, cần hoàn thiện khả năng tái lập, chống giả mạo, tích hợp các thành phần phía máy khách, hạ tầng triển khai và quản trị dữ liệu.
