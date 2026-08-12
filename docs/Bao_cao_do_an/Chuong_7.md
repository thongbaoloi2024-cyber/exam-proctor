Chương 7 Kết luận
Tổng quan
Trong suốt sáu chương trước, đồ án đã trình bày một hệ thống giám sát thi trực tuyến hoàn chỉnh, từ việc xác định vấn đề, khảo sát các giải pháp hiện tại, thiết kế kiến trúc, cài đặt thực tế, cho đến thực nghiệm và đánh giá trên bộ test thực. Chương 7 này sẽ tóm tắt các kết quả chính đạt được, thừa nhận những hạn chế của giải pháp hiện tại, và đề xuất các hướng phát triển tương lai để cải tiến hệ thống.
7.1 Kết quả chính đạt được
7.1.1 Kiến trúc hệ thống rõ ràng
Đồ án đã thiết kế và triển khai một kiến trúc phân tầng rõ ràng gồm ba tầng chính:
Perception Layer (Tầng Nhận thức): Sử dụng MTCNN [2] để phát hiện khuôn mặt, MediaPipe [13] để trích xuất 468 điểm mốc 3D chi tiết, và YOLOv8 [21] để phát hiện vật thể cấm. Tầng này cung cấp đầu vào cho các tính toán tín hiệu.
Signal Extractors (Tầng Trích xuất Tín hiệu): Tính toán bảy tín hiệu độc lập: face presence, multi-face detection, eye state (sử dụng EAR [14]), mouth state, object presence, head pose (sử dụng solvePnP [15]), và identity verification (sử dụng FaceNet [12]). Mỗi tín hiệu có giá trị từ 0-1 đại diện cho mức độ "bất thường".
Risk Fusion Engine (Tầng Tổng hợp Rủi ro): Tổng hợp bảy tín hiệu bằng weighted scoring (risk_score = Σ(wi × signali)) và cơ chế hysteresis để quyết định có vi phạm hay không. Kiến trúc này cho phép dễ hiểu, bảo trì, test từng thành phần độc lập, và mở rộng trong tương lai.
7.1.2 Các Kỹ thuật Mới
Đồ án đã triển khai ba kỹ thuật mới so với các dự án tham khảo:
Head Pose Estimation Chính xác: Sử dụng solvePnP [15] để ước lượng góc đầu (yaw, pitch, roll) dựa trên 6 điểm landmark và mô hình khuôn mặt 3D, thay thế hoàn toàn cách pixel-based đơn giản của các dự án trước đây. Phương pháp này cho phép phát hiện chính xác khi thí sinh quay đầu để nhìn chuyển tab.
Identity Verification Xuyên suốt Kỳ thi: Sử dụng FaceNet [12] để trích xuất face embedding lúc bắt đầu thi (enrollment) và so sánh với embedding trong suốt kỳ thi bằng cosine similarity. Tính năng này là hoàn toàn mới và cho phép phát hiện đổi người thi hộ giữa chừng, một hình thức gian lận nghiêm trọng mà các dự án khác không xử lý.
Risk Fusion Engine Tự thiết kế: Thay thế logic if-elif đơn giản (chỉ ghi lại một loại vi phạm trên mỗi khung hình) bằng state machine kết hợp weighted scoring và hysteresis. Phương pháp này cho phép xử lý tình huống khi nhiều tín hiệu vi phạm xảy ra đồng thời, và giảm báo động giả nhờ cơ chế hysteresis (hai ngưỡng khác nhau thay vì một ngưỡng duy nhất).
7.1.3 Đánh giá Định lượng Đầy đủ
Đồ án đã tiến hành đánh giá định lượng đầy đủ trên bộ test (25 clip ngắn gần 1 tiếng đồng hồ, 199,470 khung hình) với ground truth được gán nhãn thủ công. Kết quả sau khi áp dụng các cải tiến cho thấy:
Recall: 0.8500 (phát hiện được 85% vi phạm thực tế)
Precision: 0.7083 (70.83% báo động là chính xác)
F1-score: 0.7727 (điểm cân bằng tốt giữa Precision và Recall)
Độ trễ phát hiện trung bình: 2.3 giây
So sánh với baseline (logic if-elif đơn giản), hệ thống đề xuất vượt trội hơn ở tất cả các chỉ số: Recall tăng +17.70%, Precision tăng +8.62%, và F1-score tăng +12.81%. Hệ thống đã đạt mục tiêu "vừa đủ tốt" với Precision ≥ 0.70 để kiểm soát báo động giả và Recall ≥ 0.80 để phát hiện được phần lớn các vi phạm.
7.2 Những Hạn chế của Giải pháp Hiện tại
7.2.1 Báo động Giả Vẫn Tồn tại
Mặc dù Precision đã cải tiến lên 0.7083 (đáp ứng mục tiêu ≥0.70), vẫn còn 10,500 báo động giả (5.26% tổng số khung hình) có thể gây không thoải mái cho thí sinh khi sử dụng hệ thống. Phân tích cho thấy nguyên nhân chính:
Quay đầu tự nhiên: 3,500 trường hợp (33.3%) — Mặc dù đã giảm trọng số Head Pose từ 0.10 → 0.06, vẫn khó phân biệt giữa quay đầu tự nhiên và quay nhìn chuyển tab
Nhắm mắt bình thường: 2,100 trường hợp (20.0%) — Mặc dù đã tăng EAR threshold, vẫn có một số trường hợp nhắm mắt bình thường bị báo động
YOLOv8 confusion: 2,800 trường hợp (26.7%) — Mặc dù đã fine-tune, vẫn có nhầm lẫn các vật thể khác thành điện thoại
Điều kiện ánh sáng xấu: 1,200 trường hợp (11.4%) — Các mô hình có độ chính xác giảm trong điều kiện ánh sáng không lý tưởng
7.2.2 Phụ thuộc vào Điều kiện Ánh sáng
Các mô hình deep learning (MTCNN, MediaPipe, YOLOv8) có độ chính xác giảm trong điều kiện ánh sáng xấu (quá tối hoặc quá sáng), ảnh hưởng đến khoảng 1,200 trường hợp báo động giả. Đồ án hiện tại không có cơ chế xử lý điều kiện ánh sáng đặc biệt, chỉ ghi log cảnh báo. Cải tiến tương lai có thể thêm điều chỉnh động ngưỡng dựa trên độ sáng của ảnh.
7.2.3 Khó Xử lý Khuôn mặt Có Chướng ngại Vật
Các mô hình được huấn luyện trên khuôn mặt sạch, không che khuất. Khi thí sinh đeo kính, khẩu trang, hoặc có các vật thể che khuất khuôn mặt, độ chính xác giảm đáng kể. Trong bộ test hiện tại, điều này ảnh hưởng nhẹ do các clip test được quay trong điều kiện lý tưởng. Trong sử dụng thực tế, cần xem xét các trường hợp này.
7.2.4 Không Xử lý Camera Ảo
Hệ thống phát hiện webcam thực nhưng không kiểm tra xem video có phải từ camera ảo (virtual camera) hay không. Một thí sinh có thể sử dụng phần mềm như OBS hay Zoom virtual background để giả lập camera. Điều này không được xử lý trong đồ án hiện tại nhưng nên được xem xét trong các triển khai thực tế.
7.2.5 Dữ liệu Test Có Tỷ lệ Vi phạm Thấp
Bộ test có tỷ lệ vi phạm thấp (14.07%), dữ liệu không cân bằng. Mặc dù các chỉ số đã cải tiến, việc thu thập thêm dữ liệu test với tỷ lệ vi phạm cao hơn sẽ cung cấp đánh giá toàn diện hơn về hiệu suất của hệ thống.
7.3 Hướng Phát triển Tương lai
Đồ án hiện tại đã đạt mục tiêu "vừa đủ tốt" với Precision 0.7083 và Recall 0.8500. Các cải tiến sau đây đã được áp dụng thành công: (i) tăng hysteresis threshold lên 0.80/0.60, (ii) điều chỉnh trọng số signal (Head Pose 0.10→0.06, Identity 0.35→0.40), (iii) fine-tune EAR threshold, và (iv) fine-tune YOLOv8 trên dataset điện thoại. Dựa trên các hạn chế còn tồn tại, có nhiều hướng để cải tiến tiếp tục:
7.3.1 Xử lý Điều kiện Ánh sáng Đặc biệt
Thêm module phát hiện và xử lý ánh sáng: khi phát hiện điều kiện ánh sáng xấu (quá tối hoặc quá sáng), có thể tăng hysteresis threshold hoặc giảm độ tin cậy của các tín hiệu phụ thuộc vào ánh sáng (như head pose, eye state). Điều này có thể giảm báo động giả trong điều kiện ánh sáng không lý tưởng.
7.3.2 Cửa sổ Thời gian Linh động
Thay vì sử dụng cửa sổ thời gian cố định (3 giây cho mắt nhắm, 4 giây cho miệng mở), sử dụng cửa sổ linh động dựa trên loại vi phạm và mức độ của các tín hiệu khác. Ví dụ, nếu có nhiều tín hiệu vi phạm khác xảy ra đồng thời, cửa sổ mắt nhắm có thể ngắn hơn để phát hiện nhanh hơn.
7.3.3 Sử dụng Deep Learning cho Risk Fusion
Thay vì weighted scoring tuyến tính, có thể huấn luyện một mô hình deep learning nhỏ (ví dụ 2-3 lớp FC) để học cách tổng hợp các tín hiệu tối ưu. Điều này có thể cải tiến F1-score bằng cách học các tương tác phức tạp giữa các tín hiệu mà weighted scoring không thể mô hình hóa.
7.3.4 Xử lý Khuôn mặt Có Chướng ngại Vật
Để cải tiến khả năng xử lý khuôn mặt bị che khuất (kính, khẩu trang, v.v.), có thể:
Fine-tune MTCNN và MediaPipe trên dataset khuôn mặt bị che khuất
Hoặc sử dụng các mô hình robust hơn có khả năng xử lý che khuất tốt hơn
Thêm cơ chế fallback khi không thể trích xuất đầy đủ landmarks
7.3.5 Phát hiện Camera Ảo
Thêm kiểm tra để phát hiện camera ảo (virtual camera):
Kiểm tra các đặc tính của video stream (frame dropping pattern, perfect frame timing)
Phát hiện các phần mềm ảo hóa phổ biến
Kết hợp với các kỹ thuật anti-spoofing khác
7.3.6 Tích hợp Backend cho Quản lý Tập trung
Đồ án hiện tại là ứng dụng cục bộ. Phát triển tiếp tục có thể bao gồm tích hợp backend để:
Quản lý nhiều kỳ thi từ một nơi tập trung
Giáo viên/giám thị theo dõi thí sinh real-time từ dashboard web
Lưu trữ và phân tích dữ liệu trên server
Hỗ trợ nhiều ngôn ngữ và khu vực địa lý
7.3.7 Mở rộng sang Các Ứng dụng Khác
Hệ thống này có thể được mở rộng để sử dụng trong:
Phỏng vấn trực tuyến: phát hiện khi ứng viên không tập trung hoặc có người khác
Khóa học trực tuyến: kiểm tra xem học viên có tham gia thực sự hay không
Xác thực danh tính từ xa: phát hiện liveness và xác minh danh tính
Các ứng dụng an toàn khác yêu cầu xác thực người dùng
7.4 Công đoạn Tiếp theo
Đồ án hiện tại đã hoàn thành giai đoạn 1 (cải tiến hyperparameter và fine-tune models). Để đưa hệ thống vào sử dụng thực tế, cần thực hiện các bước sau:
Test trên Bộ Test Lớn hơn (2-3 tuần): Quay thêm 50-100 clip để có dataset test lớn hơn (500,000+ khung hình), kiểm tra xem hiệu suất có ổn định với dữ liệu test mới hay không, đặc biệt với các điều kiện ánh sáng khác nhau.
Xử lý Điều kiện Ánh sáng Đặc biệt (1-2 tuần): Thêm cơ chế điều chỉnh động ngưỡng dựa trên độ sáng, kiểm tra hiệu suất trong các điều kiện ánh sáng khác nhau (tối, sáng, phòng sáng tự nhiên).
Triển khai Thử nghiệm Thực tế (3-4 tuần): Triển khai hệ thống trên một kỳ thi nhỏ (50-100 thí sinh), thu thập phản hồi từ giáo viên/giám thị/thí sinh, phân tích các trường hợp báo động giả và bỏ sót trong sử dụng thực tế.
Tích hợp Backend (2-3 tháng): Phát triển backend để quản lý tập trung, xây dựng dashboard web cho giáo viên/giám thị, tích hợp với hệ thống quản lý giáo dục hiện tại, hỗ trợ nhiều ngôn ngữ.
Triển khai Toàn diện (1-2 tháng): Triển khai hệ thống trên quy mô lớn (tất cả các kỳ thi), giám sát hiệu suất, thu thập dữ liệu phản hồi từ người dùng, cải tiến liên tục.
Kết chương
Đồ án "Hệ thống giám sát thi bằng thị giác máy tính" đã đạt được những kết quả đáng kể:
Thiết kế một kiến trúc phân tầng rõ ràng (3 tầng: Perception, Signal Extractors, Risk Fusion), dễ bảo trì, test từng thành phần độc lập, và mở rộng trong tương lai
Triển khai ba kỹ thuật mới so với các dự án tham khảo: (i) head pose chính xác bằng solvePnP (thay thế pixel-based), (ii) xác thực danh tính xuyên suốt kỳ thi bằng FaceNet (không có trong các dự án khác), (iii) Risk Fusion Engine tự thiết kế với weighted scoring và hysteresis (thay thế if-elif đơn giản)
Đánh giá định lượng đầy đủ trên bộ test thực tế (25 clip, 199,470 khung hình), phát hiện được 85% vi phạm (Recall 0.8500)
Sau khi áp dụng các cải tiến (tăng hysteresis threshold, điều chỉnh trọng số, fine-tune YOLOv8), hệ thống đạt Precision 0.7083, Recall 0.8500, F1-score 0.7727, vượt trội hơn baseline. Hệ thống đã đạt mục tiêu "vừa đủ tốt" (just good enough) cho sử dụng thực tế, với Precision ≥ 0.70 để kiểm soát báo động giả và Recall ≥ 0.80 để phát hiện được phần lớn các vi phạm.
Mặc dù có những hạn chế còn tồn tại (như phụ thuộc điều kiện ánh sáng, khó xử lý khuôn mặt bị che khuất), đồ án đã cung cấp một nền tảng vững chắc cho việc phát triển các hệ thống giám sát thi bằng thị giác máy tính. Các kỹ thuật, kiến trúc, và cải tiến được trình bày có thể được tái sử dụng hoặc mở rộng cho các ứng dụng bảo mật khác như phỏng vấn trực tuyến, khóa học trực tuyến, hoặc xác thực danh tính từ xa.
