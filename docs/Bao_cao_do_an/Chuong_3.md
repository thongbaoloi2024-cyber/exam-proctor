Chương 3 Khảo Sát Và Phân Tích Yêu Cầu
Tổng quan
Chương 2 đã trình bày các cơ sở lý thuyết về thị giác máy tính, phát hiện khuôn mặt, trích xuất landmark, ước lượng góc đầu, xác thực danh tính, và các kỹ thuật xử lý tín hiệu. Những kiến thức này là nền tảng để hiểu các giải pháp hiện có trong lĩnh vực giám sát thi trực tuyến. Chương 3 này sẽ trình bày các nghiên cứu và sản phẩm hiện tại, bao gồm các sản phẩm thương mại phổ biến, các dự án mã nguồn mở, và các kỹ thuật liên quan được công bố trong các bài báo học thuật. Thông qua việc so sánh và đánh giá các giải pháp này, chương sẽ xác định rõ những hạn chế của các phương pháp hiện tại, từ đó làm rõ động lực và mục tiêu của đồ án này.
3.1 Các sản phẩm thương mại
3.1.1 Proctorio, Honorlock, ProctorU
Proctorio là một trong những sản phẩm giám sát thi trực tuyến phổ biến nhất, được sử dụng bởi hàng trăm ngàn sinh viên trên thế giới. Nó hoạt động dưới dạng một tiện ích mở rộng (extension) trình duyệt, cho phép ghi hình toàn màn hình, ánh sáng xung quanh, âm thanh, webcam, và theo dõi các hành động trình duyệt như chuyển tab, tải trang web mới, copy-paste. Tương tự, Honorlock cung cấp các tính năng giám sát với khả năng phát hiện việc sử dụng máy tính thứ hai. ProctorU kết hợp công nghệ tự động với giám thị con người theo dõi trực tiếp.
Tuy nhiên, các sản phẩm này không công bố chi tiết về các thuật toán của chúng. Điều này khiến khó đánh giá độ tin cậy, công bằng, tỷ lệ báo động giả, và khả năng tùy chỉnh. Bên cạnh đó, chúng là các sản phẩm thương mại có phí cao, khiến nhiều tổ chức giáo dục, đặc biệt là ở các nước đang phát triển, không thể sử dụng. Việc ghi hình toàn màn hình cũng đặt ra những vấn đề về quyền riêng tư
3.2 Các dự án mã nguồn mở
Exam-cheating-detection là một dự án mã nguồn mở phổ biến được phát triển bởi AarambhDevHub trên GitHub. Dự án này xây dựng một hệ thống giám sát thi bằng Python, sử dụng OpenCV, MediaPipe, MTCNN, facenet-pytorch, và YOLOv8. Dự án phát hiện các hành vi như: vắng mặt khuôn mặt, nhiều khuôn mặt, trạng thái mắt (EAR), trạng thái miệng, và vật thể cấm (YOLOv8). Nó cũng cung cấp một kỹ thuật liveness detection đơn giản—yêu cầu thí sinh nhắm và mở mắt liên tiếp.
Ưu điểm của exam-cheating-detection là: mã nguồn mở, dễ cài đặt, miễn phí, không phụ thuộc vào dịch vụ bên thứ ba. Tuy nhiên, nó có những hạn chế lớn: (i) logic phát hiện chỉ dựa trên các ngưỡng cứng và if-elif, dễ báo động giả; (ii) khi phát hiện một hành vi, chỉ ghi lại loại đó mà bỏ sót các loại khác xảy ra đồng thời; (iii) ước lượng góc đầu chỉ dựa trên pixel, không chính xác khi đầu quay lớn; (iv) không có khả năng xác thực danh tính để phát hiện đổi người; (v) không có đánh giá định lượng trên bộ dữ liệu test có ground truth; (vi) báo cáo cơ bản.
3.3 Các kỹ thuật liên quan 
3.3.1 Head Pose Estimation
Head pose estimation được nghiên cứu sâu với nhiều phương pháp: (i) Landmark-based methods sử dụng solvePnP [15] để ước lượng góc đầu từ các điểm mốc; (ii) CNN-based methods dự đoán trực tiếp góc đầu từ hình ảnh; (iii) Regression-based methods coi head pose như một bài toán hồi quy. Các nghiên cứu gần đây tập trung vào xử lý các tình huống khó như khuôn mặt bị che khuất hoặc góc quay lớn.
3.3.2 Face Verification và Sensor Fusion
Face verification sử dụng FaceNet [12], ArcFace, CosFace để học face embedding. Các phương pháp này đạt độ chính xác rất cao (>99%) trên benchmark nhưng nhạy cảm với điều kiện ánh sáng, góc quay, và biểu cảm.
Sensor fusion [20] tổng hợp nhiều tín hiệu bằng weighted averaging, voting, Bayesian fusion, hoặc Kalman filter. Weighted scoring là phương pháp phổ biến nhất trong các hệ thống thực tế do tính đơn giản và hiệu quả.
3.4 So sánh và phân tích hạn chế
Bảng dưới đây tóm tắt so sánh các giải pháp:
Bảng 2 So sánh các giải pháp
Đặc điểm	Proctorio	Honorlock	ProctorU	Exam-cheating-detection
Loại	Thương mại	Thương mại	Thương mại	Mã nguồn mở
Chi phí	Cao	Cao	Cao	Miễn phí
Công khai thuật toán	Không	Không	Không	Có
Head pose chính xác	Không rõ	Không rõ	Không rõ	Pixel-based (kém)
Identity verification	Không rõ	Không rõ	Không rõ	Không có
Tổng hợp tín hiệu	Không rõ	Không rõ	Không rõ	If-elif (đơn giản)
Đánh giá định lượng	Không công bố	Không công bố	Không công bố	Không có
Các hạn chế chính của các giải pháp hiện tại là: (i) thiếu tính minh bạch về thuật toán; (ii) head pose estimation không chính xác; (iii) không có xác thực danh tính; (iv) tổng hợp tín hiệu đơn giản; (v) không có đánh giá định lượng trên bộ test chuẩn; (vi) ghi hình toàn màn hình gây lo ngại quyền riêng tư; (vii) không đánh giá tỷ lệ báo động giả.
Kết chương
Chương 3 đã khảo sát các giải pháp hiện tại cho giám sát thi trực tuyến, xác định được các hạn chế chính: thiếu tính minh bạch, head pose estimation không chính xác, không có xác thực danh tính để phát hiện đổi người, tổng hợp tín hiệu đơn giản, và thiếu đánh giá định lượng. Những hạn chế này chính là động lực cho việc phát triển một giải pháp mới, được trình bày chi tiết trong Chương 4 (Thiết kế Hệ thống). Giải pháp này sẽ khắc phục các hạn chế trên bằng cách sử dụng ước lượng góc đầu chính xác (solvePnP), xác thực danh tính (FaceNet embedding), tổng hợp tín hiệu thông minh (Risk Fusion Engine), và đánh giá định lượng đầy đủ trên một bộ dữ liệu test (25 clip ngắn gần 1 tiếng đồng hồ) có ground truth.
