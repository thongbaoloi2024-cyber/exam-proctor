Chương 2 Cơ sở lý thuyết
Tổng quan
Chương 1 đã trình bày vấn đề cần giải quyết: xây dựng một hệ thống giám sát thi trực tuyến có độ tin cậy cao, khắc phục các hạn chế của các phương pháp hiện tại. Để triển khai được một hệ thống như vậy, cần nắm vững các kiến thức lý thuyết cơ bản về thị giác máy tính, xử lý ảnh, xử lý tín hiệu, và các phương pháp tổng hợp dữ liệu. Chương này sẽ trình bày các cơ sở lý thuyết cần thiết như một nền tảng để hiểu các kỹ thuật được sử dụng trong đồ án. Các nội dung chính bao gồm: (i) các khái niệm cơ bản về thị giác máy tính; (ii) các phương pháp phát hiện khuôn mặt; (iii) trích xuất các điểm mốc khuôn mặt (landmark detection); (iv) ước lượng góc đầu; (v) xác thực danh tính bằng face embedding; (vi) phát hiện các trạng thái của mắt và miệng; (vii) phát hiện vật thể; (viii) các kỹ thuật xử lý tín hiệu và state machine; và (ix) các phương pháp tổng hợp đa tín hiệu.
2.1 Khái niệm cơ bản về Thị giác máy tính
2.1.1 Định nghĩa và mục tiêu
Thị giác máy tính (computer vision) là một lĩnh vực của trí tuệ nhân tạo tập trung vào việc cho phép máy tính "nhìn" và "hiểu" thế giới thực qua các hình ảnh hoặc video. Mục tiêu cơ bản của thị giác máy tính là trích xuất thông tin hữu ích từ các dữ liệu hình ảnh (pixel data) thô, rồi chuyển đổi nó thành dạng mà máy tính có thể xử lý, phân tích, và ra quyết định [5]. Quá trình này thường được gọi là "quá trình hiểu ảnh" (image understanding), trong đó dữ liệu pixel một chiều được chuyển đổi thành các khái niệm ngữ nghĩa cao hơn mà con người có thể hiểu.
Quá trình xử lý hình ảnh trong thị giác máy tính thường bao gồm ba bước chính:
Bước 1: thu nhập dữ liệu (image acquisition). Bước này liên quan đến việc thu thập hình ảnh hoặc video từ các nguồn khác nhau như camera, webcam, hoặc ảnh tĩnh được lưu trữ. Chất lượng của dữ liệu thu nhập trực tiếp ảnh hưởng đến kết quả của các bước tiếp theo, vì vậy việc lựa chọn độ phân giải thích hợp, điều chỉnh các thông số camera, và đảm bảo điều kiện ánh sáng tốt là rất quan trọng.
Bước 2: xử lý và phân tích hình ảnh (image processing and analysis). Bước này áp dụng các kỹ thuật xử lý để trích xuất các đặc trưng quan trọng từ hình ảnh thô. Các kỹ thuật này có thể là đơn giản, như điều chỉnh độ sáng (brightness), tương phản (contrast), hoặc lọc nhiễu, hoặc phức tạp hơn, như phát hiện cạnh (edge detection), phân khúc ảnh (image segmentation), hoặc trích xuất các điểm đặc biệt (keypoint detection).
Bước 3: hiểu biết về nội dung (semantic understanding). Bước cuối cùng chuyển đổi các đặc trưng trích xuất thành các khái niệm có ý nghĩa mà con người có thể hiểu. Ví dụ, thay vì chỉ có một tập hợp các giá trị pixel, hệ thống sẽ xác định được "có một khuôn mặt ở vị trí (x, y)", "khuôn mặt này thuộc người A", hoặc "người này đang nhắm mắt". Đây là phần khó nhất của thị giác máy tính vì yêu cầu sự kết hợp giữa các kỹ thuật học máy, toán học, và kiến thức miền (domain knowledge).
2.1.2 Biểu diễn dữ liệu hình ảnh trong máy tính
Một hình ảnh hay khung hình từ video có thể được biểu diễn dưới dạng một ma trận các số. Trong trường hợp đơn giản nhất, một ảnh đen trắng (grayscale image) có thể được biểu diễn dưới dạng một ma trận hai chiều, trong đó mỗi phần tử (pixel) chứa một giá trị từ 0 đến 255, đại diện cho mức độ sáng từ đen (0) đến trắng (255).
Tuy nhiên, hầu hết các ứng dụng thực tế làm việc với ảnh màu (color image), trong đó mỗi pixel được biểu diễn bằng ba giá trị số, tương ứng với ba kênh màu RGB (Red, Green, Blue). Do đó, một ảnh màu có thể được biểu diễn dưới dạng một ma trận ba chiều với kích thước chiều rộng × chiều cao × 3. Mỗi kênh màu có giá trị từ 0 đến 255, nên tổng cộng có 256³ ≈ 16.7 triệu màu có thể được biểu diễn.
Ví dụ cụ thể: một hình ảnh có độ phân giải 640×480 pixel (chiều rộng × chiều cao) sẽ là một ma trận kích thước 640×480×3. Tổng cộng, ma trận này chứa 640×480×3 = 921,600 giá trị số. Khi xử lý ảnh hay video real-time (30 khung hình/giây), máy tính phải xử lý 640×480×3×30 ≈ 27.6 triệu giá trị mỗi giây, đó là lý do tại sao các kỹ thuật tối ưu hóa và sử dụng GPU (Graphics Processing Unit) là cần thiết.
2.1.3 Các phương pháp trong thị giác máy tính
Thị giác máy tính sử dụng nhiều phương pháp toán học và mô hình để trích xuất các đặc trưng có ý nghĩa từ ma trận pixel. Những phương pháp này có thể được phân thành ba nhóm lớn:
Phương pháp cổ điển (classical methods):
Những phương pháp này đã được phát triển từ thập niên 1970-2000 và dựa trên các nguyên lý toán học rõ ràng. Chúng bao gồm:
•	Xử lý ảnh cơ bản: Gaussian blur (làm mờ hình ảnh), edge detection (phát hiện cạnh) sử dụng toán tử Canny hoặc Sobel, corner detection (phát hiện góc) sử dụng toán tử Harris.
•	Trích xuất đặc trưng: HOG (Histogram of Oriented Gradients) tính toán histogram các hướng của gradient tại các vị trí khác nhau trong ảnh; SIFT (Scale-Invariant Feature Transform) [6] phát hiện các điểm đặc trưng bất biến với tỷ lệ và góc quay; SURF (Speeded Up Robust Features) là một phiên bản nhanh hơn của SIFT.
•	Phương pháp phát hiện: Haar Cascade [1] sử dụng cascade của các bộ phân loại Haar được huấn luyện bằng Adaboost; Deformable Part Models (DPM) mô hình vật thể thành các bộ phận có thể biến dạng.
Ưu điểm của các phương pháp cổ điển là chúng nhanh, tiết kiệm tài nguyên tính toán, và có thể hiểu được tại sao chúng hoạt động như vậy. Nhược điểm là chúng kém chính xác hơn các phương pháp hiện đại, đặc biệt là trong các tình huống phức tạp hoặc có nhiều biến thể.
Phương pháp học máy (machine learning methods):
Những phương pháp này sử dụng các mô hình học máy để học các mẫu từ dữ liệu huấn luyện. Chúng bao gồm:
•	Support Vector Machines (SVM): Một mô hình phân loại tìm siêu phẳng tối ưu để tách các lớp dữ liệu.
•	Random Forests: Một tập hợp các cây quyết định được kết hợp để đưa ra quyết định chung.
•	Boosting methods: Các phương pháp như Adaboost kết hợp nhiều bộ phân loại yếu để tạo một bộ phân loại mạnh.
Các phương pháp học máy này cải thiện so với các phương pháp cổ điển nhưng vẫn kém so với các phương pháp học sâu hiện đại.
Phương pháp học sâu (deep learning methods):
Những phương pháp này sử dụng các mạng neural sâu và là những phương pháp tiên tiến nhất hiện nay. Chúng bao gồm:
•	Convolutional Neural Networks: Được phát triển từ lần đầu bởi LeCun et al. (1989), sau đó được cải tiến thông qua nhiều kiến trúc khác nhau. VGGNet [8] sử dụng các khối convolutional với kích thước filter nhỏ (3×3) nhưng nhiều lớp. ResNet giới thiệu các kết nối tắt (skip connections) để cho phép huấn luyện các mạng rất sâu. Inception sử dụng các khối convolutional song song với kích thước filter khác nhau.
•	Region-based CNN: R-CNN [10] đề xuất các vùng (region proposal) và sau đó phân loại từng vùng. Fast R-CNN cải tiến việc tính toán bằng cách tính feature map một lần rồi trích xuất các tính năng cho mỗi vùng đề xuất. Faster R-CNN [11] thêm Region Proposal Network (RPN) để tạo ra các đề xuất một cách hiệu quả hơn.
•	Single Shot Detection (SSD): YOLO (You Only Look Once) [3] phát hiện tất cả các vật thể trong ảnh bằng một lần forward pass duy nhất. SSD tương tự nhưng sử dụng các feature map ở nhiều tỷ lệ khác nhau. RetinaNet giới thiệu focal loss để xử lý sự mất cân bằng lớp (class imbalance) giữa các bộ phân loại dương tính (background) và âm tính (objects).
•	Các mô hình khác: U-Net được sử dụng cho semantic segmentation (phân khúc ngữ nghĩa). Vision Transformer (ViT) áp dụng kiến trúc transformer, được phát triển thành công trong xử lý ngôn ngữ tự nhiên, vào thị giác máy tính.
Trong đồ án này, chúng ta sẽ sử dụng chủ yếu các phương pháp học sâu (deep learning) kết hợp với một số phương pháp cổ điển (như ước lượng góc đầu bằng solvePnP).
2.2 Phát hiện khuôn mặt
2.2.1 Tầm quan trọng và định nghĩa
Phát hiện khuôn mặt (face detection) là bước đầu tiên và rất quan trọng trong mọi hệ thống xử lý khuôn mặt [7]. Mục tiêu chính của phát hiện khuôn mặt là xác định xem trong một bức ảnh hay khung hình video có chứa một hoặc nhiều khuôn mặt hay không, và nếu có, hãy xác định vị trí cụ thể (bounding box) của chúng. Bounding box thường được biểu diễn dưới dạng (x, y, w, h), trong đó (x, y) là tọa độ góc trái trên của hộp, w là chiều rộng, và h là chiều cao.
Tại sao phát hiện khuôn mặt lại quan trọng? Vì các bước tiếp theo trong pipeline xử lý khuôn mặt (như landmark detection, face recognition, emotion detection) đều phụ thuộc vào việc đã phát hiện được khuôn mặt chính xác hay chưa. Nếu phát hiện sai lầm (bỏ sót khuôn mặt hoặc phát hiện nhầm vật thể khác là khuôn mặt), các bước tiếp theo sẽ cho kết quả sai. Hơn nữa, trong bối cảnh giám sát thi trực tuyến của đồ án, phát hiện khuôn mặt chính xác là tiền đề để có thể phát hiện được các hành vi gian lận như vắng mặt, nhiều người, hoặc đổi người.
2.2.2 Lịch sử phát triển
Phát hiện khuôn mặt là một bài toán được nghiên cứu từ thập niên 1990. Có nhiều phương pháp được phát triển qua các năm, từ những phương pháp cổ điển đến các phương pháp học sâu hiện đại [7]:
Giai đoạn 1: Phương pháp cổ điển (1990s-2000s)
•	Haar Cascade Classifiers: được đề xuất bởi Viola và Jones [1] vào năm 2001, phương pháp này sử dụng cascade của các bộ phân loại Haar (Haar-like features) được huấn luyện bằng Adaboost. Đây là một phương pháp đột phá lúc bấy giờ và được sử dụng rộng rãi trong OpenCV đến ngày nay. Ưu điểm: nhanh, tài nguyên ít, phù hợp cho các ứng dụng real-time. Nhược điểm: độ chính xác kém hơn các phương pháp hiện đại, khó xử lý các tình huống khó như khuôn mặt bị quay với góc lớn, che khuất một phần, hoặc chiếu sáng không tốt.
•	HOG: Một phương pháp trích xuất đặc trưng được sử dụng kết hợp với SVM để phát hiện người (thư viện dlib) [9]. Phương pháp này cũng có thể được sử dụng cho phát hiện khuôn mặt. Ưu điểm: tương đối chính xác. Nhược điểm: chậm hơn Haar Cascade, vẫn kém so với các phương pháp học sâu.
Giai đoạn 2: Phương pháp học sâu (2010s)
•	Region-based CNN: R-CNN [10] được đề xuất bởi Girshick et al. (2014) là phương pháp đột phá đầu tiên sử dụng deep learning cho phát hiện vật thể. Phương pháp này sau đó được áp dụng cho phát hiện khuôn mặt. R-CNN sử dụng region proposal (đề xuất vùng) để tìm các vùng có khả năng chứa vật thể, rồi phân loại từng vùng bằng CNN. Ưu điểm: chính xác cao. Nhược điểm: chậm (phải chạy CNN cho mỗi region proposal).
•	Fast R-CNN: Cải tiến của R-CNN bằng cách tính feature map một lần rồi trích xuất các tính năng cho mỗi region proposal, nhanh hơn nhiều so với R-CNN gốc.
•	Faster R-CNN [11]: Thêm Region Proposal Network (RPN) để tạo ra các region proposal một cách hiệu quả hơn. Phương pháp này trở thành một trong những phương pháp phát hiện vật thể tốt nhất và được sử dụng rộng rãi.
•	YOLO [3]: Được đề xuất bởi Redmon et al. (2016), YOLO là một phương pháp single-shot detection cho phép phát hiện nhanh tất cả các vật thể trong ảnh bằng một lần forward pass duy nhất. Mặc dù YOLO được thiết kế cho phát hiện vật thể chung (chó, mèo, xe, v.v.), nó cũng có thể được huấn luyện cho phát hiện khuôn mặt bằng fine-tuning trên dataset khuôn mặt. Ưu điểm: rất nhanh, phù hợp cho real-time. Nhược điểm: độ chính xác kém hơn Faster R-CNN, đặc biệt là với các khuôn mặt nhỏ.
•	SSD: Tương tự như YOLO, là một phương pháp single-shot, nhưng sử dụng các feature map ở nhiều tỷ lệ khác nhau để phát hiện các vật thể có kích thước đa dạng.
•	MTCNN Được thiết kế đặc biệt cho phát hiện khuôn mặt, được giới thiệu bởi Zhang et al. [2] vào năm 2016. Phương pháp này sẽ được trình bày chi tiết ở mục 2.2.3.
•	RetinaFace: Một phương pháp phát hiện khuôn mặt hiện đại [4] được đề xuất bởi Deng et al. (2020), kết hợp các ý tưởng từ Faster R-CNN với FPN (Feature Pyramid Network) để xử lý khuôn mặt có kích thước đa dạng.
2.2.3 Multi-task Cascaded Convolutional Networks
Multi-task Cascaded Convolutional Networks (MTCNN) [2] là một trong những phương pháp phát hiện khuôn mặt tốt nhất và được sử dụng rộng rãi. Nó được thiết kế để hoạt động tốt trong các tình huống khó như khuôn mặt bị che khuất một phần, góc quay lớn, hoặc chiếu sáng không tốt. MTCNN được phát triển với hai đặc điểm chính: (i) sử dụng cascade (tầng xếp tầng) của nhiều mạng CNN, và (ii) mỗi mạng giải quyết nhiều nhiệm vụ (multi-task) cùng lúc.
Kiến trúc của MTCNN:
MTCNN bao gồm ba giai đoạn (stage), mỗi giai đoạn là một mạng CNN riêng biệt. Ba giai đoạn này được thiết kế để dần dần tinh chỉnh các kết quả:
Giai đoạn 1: Proposal Network (P-Net)
Mục tiêu: Tạo ra các hộp đề xuất ban đầu (region proposal) có thể chứa khuôn mặt.
Quá trình hoạt động:
•	Đầu vào: Hình ảnh gốc với các kích thước khác nhau (image pyramid). Tại mỗi kích thước, P-Net quét qua toàn bộ hình ảnh với sliding window kích thước 12×12.
•	Tính toán: Tại mỗi vị trị sliding window, mạng P-Net tính toán ba đầu ra: (i) xác suất có khuôn mặt tại vị trí này (face probability); (ii) tọa độ điều chỉnh bounding box (bounding box regression); (iii) tọa độ của 5 điểm mốc khuôn mặt sơ bộ (landmark regression).
•	Loại bỏ: Các hộp có xác suất < ngưỡng (thường 0.5) được loại bỏ. Các hộp còn lại được hợp nhất (NMS - Non-Maximum Suppression) để loại bỏ các hộp trùng lặp.
•	Đầu ra: Một danh sách các hộp đề xuất có xác suất cao và các điểm mốc sơ bộ.
Giai đoạn 2: Refine Network (R-Net)
Mục tiêu: Loại bỏ các hộp đề xuất sai lầm (false positives) và tinh chỉnh vị trí cũng như các điểm mốc của các hộp còn lại.
Quá trình hoạt động:
•	Đầu vào: Các hộp đề xuất từ P-Net. Các hộp này được cắt từ hình ảnh gốc và resize về kích thước chuẩn 24×24.
•	Tính toán: R-Net là một mạng CNN lớn hơn P-Net, có kiến trúc tương tự nhưng với nhiều lớp hơn. Nó tính toán ba đầu ra: face probability, bounding box regression, và landmark regression.
•	Loại bỏ: Các hộp có xác suất < ngưỡng được loại bỏ. Các hộp còn lại được hợp nhất bằng NMS.
•	Tinh chỉnh: Bounding box và các điểm mốc được tinh chỉnh dựa trên đầu ra của R-Net.
•	Đầu ra: Một danh sách nhỏ hơn các hộp có chất lượng cao.
Giai đoạn 3: Output Network (O-Net)
Mục tiêu: Tạo ra kết quả cuối cùng với độ chính xác cao nhất và trích xuất chính xác 5 điểm mốc khuôn mặt.
Quá trình hoạt động:
•	Đầu vào: Các hộp đề xuất từ R-Net, được resize về kích thước chuẩn 48×48 (kích thước cao nhất trong ba giai đoạn, cho phép phát hiện chi tiết hơn).
•	Tính toán: O-Net là mạng lớn nhất trong ba giai đoạn. Nó tính toán bốn đầu ra:
o	Face probability: xác suất có khuôn mặt
o	Bounding box regression: điều chỉnh vị trí bounding box
o	Face landmarks: 5 điểm mốc trên khuôn mặt (cụ thể là: hai mắt, mũi, hai khoá miệng)
o	Face pose (tùy chọn): góc quay đầu
•	Đầu ra: Danh sách final các khuôn mặt được phát hiện với: vị trí bounding box, xác suất, 5 điểm mốc, và các thông tin khác.
Ưu điểm của MTCNN:
1.	Độ chính xác cao: MTCNN đạt tỷ lệ phát hiện rất cao trên nhiều benchmark, bao gồm WIDER Face dataset [18], một trong những dataset lớn nhất cho phát hiện khuôn mặt với hơn 393,703 khuôn mặt được gán nhãn.
2.	Xử lý tốt các tình huống khó: Mặc dù có cascade của ba giai đoạn, MTCNN vẫn có thể xử lý tốt các khuôn mặt bị quay với góc lớn, che khuất một phần bởi các vật khác (kính, khẩu trang), hoặc chiếu sáng không tốt (thiếu sáng hoặc quá sáng).
3.	Trích xuất landmark sơ bộ: Mỗi giai đoạn P-Net, R-Net, O-Net đều trích xuất 5 điểm mốc, và điểm mốc từ O-Net được sử dụng cho các bước xử lý tiếp theo (như ước lượng góc đầu, xác thực danh tính).
4.	Tốc độ xử lý chấp nhận được: Nhờ cascade design (loại bỏ các false positive từ sớm ở P-Net), MTCNN đạt tốc độ xử lý tương đối nhanh so với các phương pháp khác như RetinaFace, mặc dù chậm hơn YOLO.
Nhược điểm của MTCNN:
1.	Cần ba lần forward pass: Phải chạy ba mạng CNN riêng biệt (P-Net, R-Net, O-Net), tổng cộng chậm hơn single-stage methods như YOLO.
2.	Phụ thuộc vào chất lượng detection của P-Net: Nếu P-Net bỏ sót một khuôn mặt (đặc biệt là khuôn mặt nhỏ hoặc bị quay với góc rất lớn), các giai đoạn R-Net và O-Net không thể phục hồi (vì chúng chỉ làm việc trên các proposal từ P-Net).
3.	Nhạy cảm với kích thước khuôn mặt rất nhỏ: Khó phát hiện các khuôn mặt rất nhỏ trong ảnh (ví dụ khuôn mặt ở xa trong một ảnh phòng học toàn cảnh).
4.	Cần điều chỉnh các ngưỡng: Các ngưỡng xác suất (thường 0.5) được sử dụng trong P-Net, R-Net, O-Net có thể cần điều chỉnh tùy theo bài toán cụ thể (ví dụ có thể giảm ngưỡng để phát hiện khuôn mặt nhỏ hơn, nhưng điều này có thể tăng false positive).
2.2.4 So sánh các phương pháp phát hiện khuôn mặt
Bảng dưới đây tóm tắt so sánh các phương pháp phát hiện khuôn mặt chính:
Bảng 1 So sánh các phương pháp phát hiện khuôn mặt chính
Phương pháp	Loại	Độ chính xác	Tốc độ	Xử lý tình huống khó	Trích xuất landmark
Haar Cascade [1]	Cổ điển	Thấp	Rất nhanh	Kém	Không
HOG + SVM [9]	Cổ điển	Trung bình	Chậm	Kém	Không
R-CNN [10]	Deep learning	Cao	Rất chậm	Tốt	Có thể
Faster R-CNN [11]	Deep learning	Rất cao	Chậm	Rất tốt	Có thể
YOLO [3]	Deep learning	Cao	Rất nhanh	Trung bình	Không
MTCNN [2]	Deep learning	Rất cao	Chậm	Rất tốt	Có (5 điểm)
RetinaFace [4]	Deep learning	Rất cao	Chậm	Rất tốt	Có (5 điểm)
2.2.5 Lựa chọn phương pháp cho đồ án
Trong đồ án này, chúng tôi sử dụng MTCNN làm phương pháp chính để phát hiện khuôn mặt. Quyết định này dựa trên những lý do sau:
1.	Độ chính xác cao và xử lý tốt tình huống khó: MTCNN đã được chứng minh hiệu quả trong các ứng dụng thực tế của face detection, đặc biệt là khi khuôn mặt có góc quay lớn hoặc bị che khuất một phần, đây là những tình huống phổ biến trong giám sát thi trực tuyến (ví dụ thí sinh quay đầu nhìn sang bên, hoặc đeo kính).
2.	Có sẵn các thư viện Python: có các triển khai sẵn của MTCNN trong Python (thư viện mtcnn, facenet-pytorch) với giao diện dễ sử dụng, tiết kiệm thời gian phát triển.
3.	Tốc độ xử lý chấp nhận được: mặc dù chậm hơn YOLO, MTCNN vẫn có thể xử lý ở tốc độ gần real-time (15-25 khung hình/giây trên CPU thông thường, hoặc 30+ FPS trên GPU), đủ cho ứng dụng giám sát thi.
4.	Trích xuất sẵn 5 điểm landmark: MTCNN đã trích xuất 5 điểm mốc khuôn mặt chính xác, những điểm này được sử dụng trực tiếp cho các bước tiếp theo như ước lượng góc đầu (solvePnP) hoặc phát hiện trạng thái mắt (EAR).
5.	Tương thích tốt với các thư viện khác: MTCNN tương thích tốt với MediaPipe FaceMesh (sẽ được trình bày ở mục 2.3) và các thư viện khác mà đồ án sử dụng, cho phép tích hợp dễ dàng.
Nếu trong tương lai có nhu cầu tăng độ chính xác (ưu tiên hơn tốc độ), có thể xem xét RetinaFace [4]. Nếu cần tốc độ rất cao (ưu tiên hơn độ chính xác), có thể sử dụng YOLOv8 [21] với fine-tuning trên dataset khuôn mặt.
2.3 Landmark detection và mediapipe facemesh
Sau khi phát hiện được khuôn mặt, bước tiếp theo là xác định các điểm mốc (landmark) trên khuôn mặt. Các điểm mốc này là những vị trí đặc biệt như hai mắt, mũi, miệng, cằm, v.v. Landmark detection cho phép hệ thống hiểu được hình dạng, kích thước, và hướng của khuôn mặt, từ đó có thể phát hiện các hành động như nhắm mắt, mở miệng, hoặc quay đầu.
MediaPipe FaceMesh là một mô hình học sâu tiên tiến được phát triển bởi Google [13], có khả năng phát hiện 468 điểm mốc 3D trên khuôn mặt với độ chính xác cao. Thay vì chỉ phát hiện một số điểm mốc chính (như các phương pháp cổ điển có 5 hoặc 68 điểm), MediaPipe FaceMesh cung cấp một lưới 3D chi tiết của toàn bộ khuôn mặt, bao gồm các điểm trên mắt, miệng, mũi, cằm, và toàn bộ bề mặt khuôn mặt. Điều này cho phép phát hiện các biểu cảm mặt và hành động tinh vi với độ chính xác cao. Mô hình này được huấn luyện trên một tập dữ liệu lớn với các đặc điểm đa dạng (nhiều loại khuôn mặt, góc quay, điều kiện ánh sáng), giúp nó hoạt động tốt trên nhiều loại khuôn mặt khác nhau.
Trong đồ án, MediaPipe FaceMesh được sử dụng kết hợp với các phương pháp khác (như EAR cho phát hiện mắt nhắm) để tăng tính chính xác của các tín hiệu phát hiện hành vi.
2.4 Ước lượng góc đầu
Ước lượng góc đầu (head pose estimation) là khả năng xác định hướng mà đầu người đang quay, thường được biểu diễn bằng ba góc: yaw (quay trái-phải), pitch (quay lên-xuống), và roll (quay cân bằng). Phát hiện các thay đổi lớn trong góc đầu có thể chỉ ra rằng thí sinh đang nhìn sang nơi khác, có thể là nhìn ra ngoài khung hình hoặc nhìn sang một thiết bị khác.
Phương pháp Perspective-n-Point (solvePnP) là một kỹ thuật cổ điển trong thị giác máy tính để ước lượng góc đầu dựa trên tương ứng giữa các điểm 2D trên ảnh và các điểm 3D của một mô hình khuôn mặt chuẩn. Cụ thể, phương pháp này sử dụng sáu điểm landmark chính (hai mắt, mũi, hai khoé miệng, cằm) từ ảnh 2D và so khớp chúng với một mô hình khuôn mặt 3D đã được biết trước. Bằng cách giải bài toán hình học này, phương pháp solvePnP có thể tính toán chính xác các ma trận quay (rotation matrix) và vectơ chuyển dịch (translation vector), từ đó suy ra góc yaw, pitch, roll.
Ưu điểm của solvePnP so với các phương pháp khác (như chỉ dựa trên sự lệch vị trí pixel) là nó tận dụng thông tin về hình học 3D của khuôn mặt, cho phép ước lượng chính xác ngay cả khi khuôn mặt có góc quay lớn. Tuy nhiên, độ chính xác của phương pháp này phụ thuộc vào chất lượng của mô hình khuôn mặt 3D chuẩn và độ chính xác của camera intrinsic parameters (focal length, principal point, v.v.).
2.5 Xác thực danh tính bằng face embedding
Xác thực danh tính (identity verification) là khả năng xác định xem một khuôn mặt trong ảnh hiện tại có phải là cùng một người như trong ảnh tham chiếu hay không. Trong bối cảnh giám sát thi, điều này rất quan trọng để phát hiện những trường hợp đổi người thi hộ giữa chừng kỳ thi.
Face embedding là một phương pháp biểu diễn khuôn mặt dưới dạng một vector số (thường có kích thước từ 128 đến 512 chiều), trong đó những khuôn mặt của cùng một người sẽ có vector gần nhau, còn khuôn mặt của những người khác sẽ có vector cách xa nhau trong không gian embedding này. FaceNet [12] là một mô hình deep learning nổi tiếng cho việc tạo face embedding, sử dụng mạng Inception và hàm mất triplet loss để huấn luyện. Khi có hai embedding của hai khuôn mặt, có thể tính độ similarity giữa chúng bằng cosine similarity, một phép đo về góc giữa hai vector. Nếu độ similarity cao hơn một ngưỡng được đặt trước (thường 0.6), hai khuôn mặt được coi là của cùng một người.
Trong đồ án này, phương pháp facenet-pytorch được sử dụng để trích xuất face embedding. Lúc bắt đầu kỳ thi (enrollment), embedding của khuôn mặt thí sinh được tính toán và lưu trữ. Trong suốt quá trình thi, mỗi khung hình, embedding hiện tại được so sánh với embedding lúc enrollment. Nếu độ similarity rơi xuống dưới ngưỡng, có thể cảnh báo rằng danh tính có thể đã thay đổi.
2.6 Phát hiện trạng thái mắt
Phát hiện trạng thái mắt (eye state detection) là khả năng xác định xem mắt đang mở hay đang nhắm. Trong giám sát thi, nếu thí sinh nhắm mắt quá lâu hoặc quá thường xuyên, có thể chỉ ra rằng họ không tập trung vào bài thi.
Eye Aspect Ratio (EAR) [14] là một phương pháp đơn giản nhưng hiệu quả để phát hiện trạng thái mắt. EAR được tính toán bằng cách sử dụng sáu điểm landmark quanh mỗi mắt (từ MediaPipe hoặc các mô hình landmark detection khác). Công thức EAR là: EAR = (khoảng cách giữa hai điểm trên + khoảng cách giữa hai điểm dưới) / (2 × khoảng cách giữa hai điểm trái và phải). Khi mắt mở, EAR sẽ cao (thường > 0.2); khi mắt nhắm, EAR sẽ thấp (< 0.1). Bằng cách đặt một ngưỡng EAR, có thể xác định được thời điểm mắt nhắm. Tuy nhiên, EAR có thể bị ảnh hưởng bởi góc khuôn mặt và điều kiện ánh sáng, vì vậy thường cần phối hợp với các kỹ thuật khác để tăng độ tin cậy.
2.7 Phát hiện trạng thái miệng
Phát hiện trạng thái mắt (eye state detection) là khả năng xác định xem mắt đang mở hay đang nhắm. Trong giám sát thi, nếu thí sinh nhắm mắt quá lâu hoặc quá thường xuyên, có thể chỉ ra rằng họ không tập trung vào bài thi.
Eye Aspect Ratio (EAR) [14] là một phương pháp đơn giản nhưng hiệu quả để phát hiện trạng thái mắt. EAR được tính toán bằng cách sử dụng sáu điểm landmark quanh mỗi mắt (từ MediaPipe hoặc các mô hình landmark detection khác). Công thức EAR là: EAR = (khoảng cách giữa hai điểm trên + khoảng cách giữa hai điểm dưới) / (2 × khoảng cách giữa hai điểm trái và phải). Khi mắt mở, EAR sẽ cao (thường > 0.2); khi mắt nhắm, EAR sẽ thấp (< 0.1). Bằng cách đặt một ngưỡng EAR, có thể xác định được thời điểm mắt nhắm. Tuy nhiên, EAR có thể bị ảnh hưởng bởi góc khuôn mặt và điều kiện ánh sáng, vì vậy thường cần phối hợp với các kỹ thuật khác để tăng độ tin cậy.
2.8 Phát hiện vật thể
Phát hiện vật thể (object detection) là khả năng xác định các vật thể cụ thể trong một ảnh và xác định loại cũng như vị trí của chúng. Trong bối cảnh giám sát thi, các vật thể quan trọng cần phát hiện là các vật thể cấm hoặc đáng ngờ như điện thoại di động, sách, máy tính bảng, v.v.
YOLOv8 [21] là một mô hình phát hiện vật thể hiện đại, nổi tiếng vì khả năng phát hiện nhanh và chính xác. YOLO sử dụng một mạng CNN duy nhất để phát hiện tất cả các vật thể trong một ảnh cùng một lúc, thay vì các phương pháp cũ dựa trên region proposal. YOLOv8 được huấn luyện trên dataset COCO [17] lớn chứa hơn 80 loại vật thể khác nhau, bao gồm các vật thể như điện thoại, sách, laptop, v.v. Ngoài ra, YOLOv8 có thể được fine-tune trên dataset riêng để phát hiện các loại vật thể cụ thể (như điện thoại bất kỳ loại nào) với độ chính xác cao hơn.
2.9 Máy trạng thái và xử lý tín hiệu
Một máy trạng thái (state machine) là một mô hình toán học được sử dụng để mô tả hệ thống có các trạng thái rõ ràng và các chuyển đổi giữa các trạng thái. Trong bối cảnh của đồ án, state machine được sử dụng để theo dõi trạng thái của mỗi tín hiệu theo thời gian. Ví dụ, thay vì coi một khung hình duy nhất có EAR thấp là "mắt nhắm", state machine có thể theo dõi liệu mắt đã nhắm trong bao lâu rồi, và chỉ cảnh báo khi mắt nhắm liên tục trong một khoảng thời gian nhất định.
Cửa sổ thời gian trượt (sliding time window) là một kỹ thuật xử lý tín hiệu trong đó chỉ xem xét dữ liệu trong một cửa sổ thời gian cố định (ví dụ 3-5 giây gần đây nhất) thay vì toàn bộ dữ liệu từ đầu. Điều này giúp hệ thống có thể phản ứng nhanh với những thay đổi gần đây nhất mà không bị ảnh hưởng quá lâu bởi những sự kiện cũ.
2.10 Đánh giá tín hiệu
Khi có nhiều tín hiệu từ các nguồn khác nhau (mắt nhắm, miệng mở, đầu quay, vô danh tính, v.v.), cần một cách để tổng hợp chúng thành một quyết định duy nhất. Weighted scoring là một phương pháp trong đó mỗi tín hiệu được gán một trọng số (weight) thể hiện mức độ quan trọng hoặc mức độ tin cậy của tín hiệu đó. Tổng điểm cuối cùng được tính bằng tổng có trọng số của tất cả các tín hiệu.
Ví dụ, nếu phát hiện được danh tính không khớp (đổi người), trọng số của tín hiệu này có thể rất cao (ví dụ 0.9 trên tổng điểm 1.0), vì đây là hình thức gian lận rất nghiêm trọng. Ngược lại, nếu phát hiện được mắt nhắm chỉ trong 1-2 giây, trọng số có thể thấp hơn (ví dụ 0.1), vì thí sinh có thể chỉ nhắm mắt ngắn.
Hysteresis (chống dao động) là một cơ chế để tránh các quyết định thay đổi quá nhanh chóng khi điểm số gần một ngưỡng cụ thể. Thay vì sử dụng một ngưỡng duy nhất, hysteresis sử dụng hai ngưỡng: một ngưỡng "lên" (ví dụ 0.7) để chuyển từ trạng thái "bình thường" sang "cảnh báo", và một ngưỡng "xuống" (ví dụ 0.5) để chuyển ngược lại. Điều này giúp tránh tình trạng báo động giả khi điểm số dao động quanh một ngưỡng duy nhất.
Kết chương
Chương 2 đã trình bày các cơ sở lý thuyết cần thiết để hiểu các kỹ thuật được sử dụng trong đồ án. Từ các phương pháp phát hiện khuôn mặt như MTCNN, đến các kỹ thuật trích xuất landmark như MediaPipe FaceMesh, đến các phương pháp ước lượng góc đầu bằng solvePnP và xác thực danh tính bằng face embedding, các công nghệ này cung cấp nền tảng để xây dựng một hệ thống phát hiện hành vi toàn diện. Ngoài ra, các kỹ thuật xử lý tín hiệu như state machine, sliding time window, weighted scoring, và hysteresis cung cấp các công cụ để tổng hợp nhiều tín hiệu lại thành những quyết định đáng tin cậy. Những kiến thức này sẽ được áp dụng trong Chương 3 và Chương 4 để thiết kế và triển khai hệ thống giám sát thi.
