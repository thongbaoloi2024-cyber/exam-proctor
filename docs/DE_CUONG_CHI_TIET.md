# Đề cương chi tiết Đồ án tốt nghiệp

## Hệ thống Giám sát Thi trực tuyến bằng Thị giác máy tính

> Tài liệu này là đề cương chi tiết Tuần 1, dựa trên `KE_HOACH_DO_AN.md` (kiến trúc & phạm vi kỹ thuật) và `KE_HOACH_4_THANG_THEO_TUAN.md` (lộ trình thực hiện). Các mục 5-7 là phần khảo sát kỹ thuật liên quan phục vụ chương "Cơ sở lý thuyết / Related Work" của luận văn sau này.

---

## 1. Đặt vấn đề

Học tập và thi cử trực tuyến trở thành hình thức phổ biến sau giai đoạn chuyển đổi số của giáo dục, nhưng đi kèm với đó là nguy cơ gian lận thi cử khó kiểm soát khi không có giám thị trực tiếp: sử dụng tài liệu/thiết bị trái phép, trao đổi với người khác, hoặc nghiêm trọng hơn là **nhờ người khác thi hộ**. Các giải pháp giám sát thủ công (giám thị xem qua video call) tốn nhân lực, khó mở rộng theo số lượng thí sinh, và dễ bỏ sót hành vi diễn ra trong thời gian ngắn.

Các hệ thống giám sát tự động hiện có — kể cả dự án mã nguồn mở tham khảo `exam-cheating-detection` — thường dừng ở mức phát hiện dấu hiệu bề mặt (vắng mặt khuôn mặt, nhiều khuôn mặt, vật thể cấm) bằng các quy tắc ngưỡng đơn giản, và có hai hạn chế kỹ thuật rõ rệt:

1. **Không xác định được hướng nhìn thật của đầu**: các cách tiếp cận đơn giản so lệch pixel mắt–mũi trên ảnh 2D, không tính đến chiều sâu (depth) và phối cảnh camera, nên dễ sai khi thí sinh nghiêng đầu ở góc trung bình hoặc ngồi lệch tâm khung hình.
2. **Không xác thực danh tính xuyên suốt bài thi**: hệ thống chỉ đếm số khuôn mặt trong khung hình, không kiểm tra khuôn mặt đó có đúng là thí sinh đã đăng ký hay không — bỏ lọt hoàn toàn kịch bản **thi hộ giữa chừng** (đổi người sau khi giám thị/hệ thống đã xác nhận lúc đầu giờ).

Ngoài ra, việc ra quyết định cảnh báo bằng chuỗi `if/elif` có thứ tự ưu tiên (chỉ ghi nhận **một** loại vi phạm mỗi khung hình) dẫn đến bỏ sót khi nhiều dấu hiệu nghi vấn xảy ra đồng thời, và không có cơ chế chống dao động (một tín hiệu dao động quanh ngưỡng sẽ liên tục bật/tắt cảnh báo, gây nhiễu báo cáo).

Đồ án đặt vấn đề: **có thể tự thiết kế và cài đặt một pipeline thị giác máy tính khắc phục ba hạn chế trên** (ước lượng hướng đầu có cơ sở hình học 3D, xác thực danh tính liên tục bằng embedding khuôn mặt, và một cơ chế kết hợp đa tín hiệu chống báo động giả) **hay không, và cải tiến đó có đo lường được bằng số liệu định lượng so với cách tiếp cận ngưỡng đơn giản hay không.**

## 2. Mục tiêu

### 2.1. Mục tiêu tổng quát
Xây dựng một ứng dụng giám sát thi bằng webcam chạy trên một máy tính đơn (single-machine, single-student), trong đó toàn bộ pipeline nhận diện hành vi nghi vấn do sinh viên tự thiết kế và cài đặt (không sao chép code từ dự án tham khảo), có khả năng phát hiện nhiều loại hành vi gian lận với độ chính xác định lượng được, bao gồm cả trường hợp thi hộ.

### 2.2. Mục tiêu cụ thể
- **MT1.** Thiết kế và cài đặt kiến trúc pipeline 3 tầng: Perception Layer → Signal Extractors → Risk Fusion Engine (chi tiết tại `KE_HOACH_DO_AN.md`, mục 3.1).
- **MT2.** Cài đặt tối thiểu 7 signal extractor: vắng mặt khuôn mặt, nhiều khuôn mặt, trạng thái mắt (EAR), trạng thái miệng, vật thể cấm (điện thoại/sách), **head pose estimation bằng `cv2.solvePnP`**, và **xác thực danh tính bằng face embedding**.
- **MT3.** Thiết kế thuật toán **Risk Fusion Engine** tự xây dựng: state machine theo cửa sổ thời gian trượt cho từng tín hiệu, tổng hợp thành điểm rủi ro liên tục có trọng số, quyết định cảnh báo bằng ngưỡng hysteresis (2 ngưỡng lên/xuống).
- **MT4.** Xây dựng module log & báo cáo (PDF/HTML) trình bày lại toàn bộ vi phạm phát hiện được trong một phiên thi.
- **MT5.** Đánh giá định lượng: tự quay và gán nhãn bộ test (~20-30 clip), cài đặt một baseline mô phỏng logic if/elif đơn giản, so sánh Precision/Recall/F1 và độ trễ phát hiện giữa hệ thống đề xuất và baseline.

## 3. Phạm vi

### 3.1. Trong phạm vi (in-scope)
- Ứng dụng chạy **cục bộ trên một máy tính**, giám sát **một thí sinh duy nhất** qua webcam tích hợp/rời trong thời gian thực.
- Xử lý tín hiệu hình ảnh (video) và tuỳ chọn âm thanh cơ bản (voice activity detection); không xử lý nội dung bài thi hay tương tác với hệ thống thi thật.
- Hai kỹ thuật CV mới bắt buộc: head pose estimation bằng `solvePnP` và identity verification bằng face embedding (facenet-pytorch, InceptionResnetV1).
- Thuật toán Risk Fusion Engine tự thiết kế (state machine + weighted scoring + hysteresis).
- Bộ dữ liệu test tự quay, quy mô nhỏ (không phải dữ liệu huấn luyện, chỉ dùng để đánh giá).
- Sử dụng model pretrained cho các khối nền tảng (MediaPipe FaceMesh, MTCNN, YOLOv8-COCO) — đây là công cụ nền được phép dùng như mọi đồ án CV, không phải phần "đóng góp" cần đánh giá.

### 3.2. Ngoài phạm vi (out-of-scope)
- Kiến trúc client-server, nhiều người dùng đồng thời, cơ sở dữ liệu tập trung, dashboard quản trị cho giám thị (đã loại bỏ khỏi hướng đồ án từ 2026-07-15, xem lịch sử thay đổi trong `KE_HOACH_DO_AN.md`).
- Huấn luyện lại (fine-tune/train from scratch) bất kỳ mô hình deep learning nào — toàn bộ model thị giác máy tính là pretrained, phần tự làm nằm ở tầng trích xuất đặc trưng, fusion và ra quyết định.
- Calibration camera thật (dùng ma trận camera xấp xỉ theo độ phân giải ảnh — giới hạn được ghi nhận rõ trong luận văn).
- Chống giả mạo sinh trắc học nâng cao (anti-spoofing chống ảnh/video giả danh tính) — chỉ dừng ở so khớp embedding cosine similarity.
- Phát hiện gian lận qua kênh phi thị giác (chia sẻ màn hình, gõ phím, mạng).

### 3.3. Đối tượng và phạm vi ứng dụng
- **Đối tượng sử dụng dự kiến**: cơ sở giáo dục quy mô vừa/nhỏ (trường đại học, trung tâm đào tạo) tổ chức thi trực tuyến, cần công cụ hỗ trợ giám sát tự động ở mức chi phí thấp, không đòi hỏi hạ tầng server.
- **Ngữ cảnh sử dụng**: thí sinh cài đặt và chạy ứng dụng trên máy cá nhân trong lúc làm bài; giám thị/giảng viên xem lại báo cáo PDF/HTML sau khi kết thúc phiên thi (giám sát hậu kiểm, không phải can thiệp real-time).
- **Giới hạn đối tượng đánh giá**: bộ test tự quay bởi sinh viên thực hiện đồ án và một vài người hỗ trợ (bạn bè), không đại diện đầy đủ cho sự đa dạng dân số thực tế (độ tuổi, sắc tộc, điều kiện ánh sáng) — nêu rõ là hạn chế của thực nghiệm trong luận văn.

## 4. Phương pháp thực hiện

Áp dụng quy trình phát triển phần mềm lặp theo tuần (16 tuần, chi tiết tại `KE_HOACH_4_THANG_THEO_TUAN.md`): thiết kế trước khi code (Tháng 1), cài đặt Perception Layer & Signal Extractors cơ bản (Tháng 1-2), hai kỹ thuật mới trọng tâm (Tháng 2), Risk Fusion Engine & sản phẩm hoàn chỉnh (Tháng 3), đánh giá định lượng & viết luận văn (Tháng 4). Mỗi giai đoạn có kiểm thử (unit test/integration test) và demo thực tế qua webcam trước khi chuyển giai đoạn tiếp theo.

---

## 5. Khảo sát kỹ thuật liên quan

> Phần này khảo sát các **phương pháp kỹ thuật** làm cơ sở lý thuyết cho 3 thành phần cốt lõi của đồ án, không phải khảo sát sản phẩm thương mại (xem mục 6 cho phần đó).

### 5.1. Head Pose Estimation

**5.1.1. Phương pháp hình học dựa trên landmark (`cv2.solvePnP`)**

Đây là phương pháp được lựa chọn cho đồ án. Ý tưởng cốt lõi: bài toán Perspective-n-Point (PnP) tìm phép biến đổi (ma trận xoay R, vector tịnh tiến t) ánh xạ một tập điểm 3D chuẩn (canonical 3D face model) sang tập điểm 2D quan sát được trên ảnh, sao cho sai số chiếu (reprojection error) nhỏ nhất. Quy trình điển hình:

1. Trích xuất 6 điểm landmark 2D đặc trưng từ bộ dò khuôn mặt (đỉnh mũi, cằm, 2 khoé mắt ngoài, 2 khoé miệng) — với đồ án này là từ MediaPipe FaceMesh (468 điểm, xem 5.1.3).
2. Gán tương ứng 6 điểm đó với toạ độ 3D xấp xỉ trên một mô hình khuôn mặt trung bình chuẩn (không cần đo thật từng người).
3. Ước lượng ma trận nội tại camera (camera intrinsic matrix) xấp xỉ theo độ phân giải ảnh (focal length ≈ chiều rộng ảnh, principal point ở tâm ảnh) khi không có calibration thật.
4. Gọi `cv2.solvePnP` để giải ra rotation vector, dùng công thức Rodrigues chuyển sang ma trận xoay, rồi phân rã thành 3 góc Euler yaw/pitch/roll.

Ưu điểm: không cần huấn luyện, chạy nhanh (CPU thời gian thực), có ý nghĩa hình học tường minh (góc quay thật theo độ, không phải điểm số tương đối), dễ trực quan hoá (vẽ trục 3D lên khung hình) để kiểm chứng và giải thích trong luận văn.

Hạn chế đã ghi nhận trong tài liệu kỹ thuật: sai số của bộ dò landmark truyền trực tiếp vào sai số ước lượng góc; việc dùng mô hình khuôn mặt trung bình (không cá nhân hoá) gây sai số hệ thống; và bước dò landmark là một tầng tính toán riêng, tạo thêm chi phí xử lý so với phương pháp end-to-end.

**5.1.2. Phương pháp học sâu trực tiếp từ ảnh (landmark-free / keypoint-free)**

Hướng tiếp cận khác — không qua bước trung gian trích landmark — huấn luyện mạng CNN dự đoán trực tiếp góc yaw/pitch/roll từ ảnh khuôn mặt (ví dụ hướng tiếp cận phân loại góc theo bin kết hợp hồi quy như trong Ruiz & Chong, *"Fine-Grained Head Pose Estimation Without Keypoints"*, CVPR Workshops 2018). Ưu điểm: không phụ thuộc vào một mô hình khuôn mặt 3D cố định, tốc độ suy luận nhanh hơn vì bỏ qua bước dò landmark, và theo các khảo sát gần đây (Springer AI Review 2024, *"Deep learning and machine learning techniques for head pose estimation: a survey"*) đạt độ chính xác cao hơn trên các bộ benchmark chuẩn so với phương pháp landmark-to-pose truyền thống. Nhược điểm: cần dữ liệu huấn luyện gán nhãn góc thật (khó tự thu thập ở quy mô đồ án), là hộp đen khó giải thích bằng hình học, và đòi hỏi hạ tầng huấn luyện/tinh chỉnh mô hình riêng.

**5.1.3. Lựa chọn cho đồ án và lý do**

Đồ án chọn `solvePnP` thay vì huấn luyện mô hình học sâu riêng vì: (i) không cần dữ liệu huấn luyện gán nhãn góc — phù hợp ràng buộc thời gian của đồ án cử nhân/kỹ sư; (ii) có ý nghĩa hình học tường minh, dễ giải thích và trực quan hoá trước hội đồng; (iii) MediaPipe FaceMesh (Kartynnik et al., 2019 — mô hình dự đoán 468 điểm landmark 3D bề mặt khuôn mặt từ một ảnh camera đơn, chạy real-time kể cả trên thiết bị di động) đã được dùng sẵn trong pipeline cho các signal khác (EAR, mouth openness), nên tái sử dụng landmark đầu ra của nó cho head pose không phát sinh thêm chi phí dò khuôn mặt/landmark riêng. Đây chính là điểm khác biệt kỹ thuật so với dự án tham khảo (chỉ so lệch pixel mắt–mũi 2D, không có góc quay thật).

### 5.2. Face Verification (Xác thực danh tính bằng Face Embedding)

**5.2.1. Nguyên lý embedding và cosine similarity**

Thay vì phân loại khuôn mặt vào một tập lớp cố định (closed-set classification), các hệ thống face verification hiện đại học một phép ánh xạ (embedding) từ ảnh khuôn mặt sang một không gian vector chiều thấp, sao cho khoảng cách giữa hai embedding của cùng một người nhỏ, và của hai người khác nhau lớn. Việc xác minh hai ảnh có cùng là một người hay không được quy về so sánh khoảng cách/độ tương đồng giữa hai vector embedding với một ngưỡng quyết định — phổ biến nhất là cosine similarity, được tính theo tích vô hướng chuẩn hoá của hai vector.

**FaceNet** (Schroff, Kalenichenko & Philbin, *"FaceNet: A Unified Embedding for Face Recognition and Clustering"*, CVPR 2015) là công trình đặt nền móng cho hướng tiếp cận này: mạng CNN được huấn luyện trực tiếp để tối ưu embedding bằng **triplet loss** (kéo gần embedding của cặp ảnh cùng người – anchor/positive, đẩy xa embedding của ảnh người khác – negative), đạt 99.63% accuracy trên benchmark LFW. Kiến trúc InceptionResnetV1 huấn luyện trên bộ dữ liệu VGGFace2 (dùng qua thư viện `facenet-pytorch`) là một biến thể triển khai phổ biến của hướng tiếp cận này và được đồ án sử dụng trực tiếp.

**ArcFace** (Deng et al., *"ArcFace: Additive Angular Margin Loss for Deep Face Recognition"*, CVPR 2019, arXiv:1801.07698) là một hướng cải tiến sau này: thay vì triplet loss, ArcFace thêm một biên góc phụ (additive angular margin) vào hàm mất mát softmax, có diễn giải hình học rõ ràng (tương ứng khoảng cách trắc địa trên siêu cầu đơn vị), giúp embedding các lớp danh tính tách biệt hơn và đạt kết quả tốt hơn FaceNet trên các benchmark quy mô lớn (MegaFace). Đồ án chọn FaceNet/facenet-pytorch thay vì ArcFace vì có thư viện Python sẵn (`facenet-pytorch`), dễ tích hợp cho một pipeline single-machine không cần độ chính xác ở quy mô hàng triệu danh tính; ArcFace được ghi nhận là hướng mở rộng khả thi nếu cần độ chính xác cao hơn.

**5.2.2. Chọn ngưỡng quyết định (decision threshold)**

Ngưỡng cosine similarity để quyết định "cùng một người" không phải hằng số phổ quát — phụ thuộc vào mô hình, tập huấn luyện và điều kiện triển khai thực tế. Phương pháp chuẩn để chọn ngưỡng trên benchmark là dùng bộ cặp ảnh đánh giá LFW, quét ngưỡng và chọn điểm mà tỉ lệ chấp nhận sai (False Accept Rate) bằng tỉ lệ từ chối sai (False Reject Rate) — gọi là Equal Error Rate (EER) — làm điểm cân bằng giữa an toàn (không cho người lạ lọt qua) và trải nghiệm (không từ chối nhầm người thật). Trong bối cảnh đồ án (không có bộ benchmark lớn để tính EER chính xác), ngưỡng ban đầu được chọn theo kinh nghiệm thực nghiệm phổ biến trong cộng đồng `facenet-pytorch` (thường trong khoảng 0.5–0.7 tuỳ chuẩn hoá embedding), sau đó **có biên độ (margin)**: dưới ngưỡng thấp mới kết luận "đổi người", vùng giữa gắn cờ "cảnh báo nhẹ" cần theo dõi thêm — nhằm giảm false positive khi ánh sáng/góc mặt thay đổi tự nhiên trong lúc thi (rủi ro đã ghi nhận tại `KE_HOACH_DO_AN.md`, mục 5). Ngưỡng cụ thể sẽ được tinh chỉnh bằng thực nghiệm ở Tháng 4 (Tuần 14).

### 5.3. Sensor Fusion và Cơ chế Hysteresis cho hệ thống giám sát

**5.3.1. Vì sao cần fusion thay vì if/elif đơn lẻ**

Khi một hệ thống có nhiều nguồn tín hiệu độc lập (ở đây là nhiều signal extractor: mắt, miệng, vật thể, tư thế đầu, danh tính...), cách tiếp cận ngây thơ là dùng chuỗi điều kiện có thứ tự ưu tiên, chỉ báo một loại vi phạm mỗi thời điểm — đây chính là hạn chế của dự án tham khảo. Trong các lĩnh vực giám sát/báo động lâu đời hơn (theo dõi bệnh nhân ICU, hệ thống báo động IoT), tài liệu kỹ thuật cho thấy việc **kết hợp nhiều nguồn tín hiệu (sensor fusion)** — thay vì xét từng tín hiệu độc lập — giảm đáng kể tỉ lệ báo động giả. Ví dụ, các nghiên cứu về giảm báo động giả nhịp tim trong ICU dùng kết hợp tín hiệu ECG với các cảm biến khác (chất lượng tín hiệu, gia tốc kế) qua nhiều kỹ thuật (mạng nơ-ron, suy luận Bayes, logic mờ, bỏ phiếu đa số), trong đó phương pháp mạng nơ-ron kết hợp đạt mức giảm báo động giả tới ~92.5%, cao hơn hẳn cách xét tín hiệu đơn lẻ. Các hệ thống báo động dựa trên quy tắc (rule-based expert system) kết hợp nhiều nguồn cảm biến, có gán trọng số/độ tin cậy khác nhau theo từng nguồn, cũng là một hướng tiếp cận phổ biến và dễ diễn giải hơn so với các mô hình học máy phức tạp — phù hợp với quy mô đồ án.

**5.3.2. Weighted rule-based fusion**

Đồ án áp dụng hướng tiếp cận **rule-based có trọng số**: mỗi tín hiệu (signal extractor) có một state machine riêng (NORMAL → SUSPICIOUS → ALERT) đánh giá theo cửa sổ thời gian trượt, và trạng thái của các state machine được tổng hợp thành một **điểm rủi ro liên tục** bằng tổng có trọng số — trọng số phản ánh mức độ nghiêm trọng chủ quan ban đầu của từng loại vi phạm (ví dụ identity mismatch và phát hiện vật thể cấm có trọng số cao hơn chuyển động mắt), tương tự cách các hệ thống sensor fusion gán "độ tin cậy" khác nhau cho từng nguồn tuỳ hoàn cảnh. Cách tiếp cận này được chọn thay vì mô hình học máy (neural network fusion) vì: không cần dữ liệu huấn luyện lớn, dễ diễn giải nguyên nhân cảnh báo (quan trọng để giáo viên tin tưởng báo cáo), và trọng số có thể tinh chỉnh thủ công bằng thực nghiệm ở giai đoạn đánh giá (Tháng 4) mà không cần huấn luyện lại mô hình.

**5.3.3. Hysteresis chống dao động**

Một vấn đề riêng khi dùng một ngưỡng duy nhất cho tín hiệu dao động quanh biên là hiện tượng "chatter" — tín hiệu liên tục bật/tắt trạng thái cảnh báo dù giá trị chỉ dao động nhẹ quanh ngưỡng. Đây là vấn đề kinh điển trong lý thuyết điều khiển và hệ thống báo động cảm biến (ví dụ dùng ngưỡng kép trong dò chuyển động PIR kết hợp cảm biến siêu âm để loại trừ trigger giả). Giải pháp chuẩn là **hysteresis (ngưỡng kép)**: một ngưỡng cao hơn để CHUYỂN vào trạng thái cảnh báo, một ngưỡng thấp hơn để THOÁT khỏi trạng thái cảnh báo — tạo một "vùng đệm" mà tín hiệu dao động trong đó không gây chuyển trạng thái liên tục. Đồ án áp dụng nguyên lý này ở tầng tổng hợp điểm rủi ro cuối cùng (Risk Fusion Engine), là điểm khác biệt thứ ba so với dự án tham khảo (vốn không có cơ chế chống dao động).

---

## 6. Khảo sát nhanh sản phẩm thương mại (bối cảnh ứng dụng)

> Phần này chỉ nhằm minh hoạ bối cảnh ứng dụng thực tế của bài toán, **không phải trọng tâm khảo sát kỹ thuật** (xem mục 5).

Trên thị trường hiện có nhiều nền tảng giám sát thi trực tuyến thương mại quy mô lớn. **Proctorio** là nền tảng giám sát hoàn toàn tự động (fully automated), hoạt động dưới dạng tiện ích mở rộng trình duyệt Chrome, dùng phân tích hành vi bằng AI để theo dõi phiên thi mà không cần giám thị người, với hơn 20 tuỳ chọn cấu hình giám sát (khoá trình duyệt, ghi webcam/âm thanh, theo dõi màn hình, gắn cờ hành vi) và cơ chế "Suspicion Score" (điểm nghi vấn theo màu đỏ/vàng/xanh) giúp giảng viên ưu tiên phiên nào cần xem lại. **Honorlock** theo hướng lai (hybrid): AI giám sát hành vi, phát hiện điện thoại/thiết bị thứ hai và giọng nói theo thời gian thực, khi phát hiện dấu hiệu nghi vấn mới chuyển cho giám thị người xem lại và can thiệp — đồng thời có cơ chế điều chỉnh mức độ giám sát thích ứng theo hành vi để giảm báo động giả. Điểm chung của cả hai nền tảng là mô hình **client-server đa người dùng** với hạ tầng backend lớn, khác biệt căn bản với phạm vi đồ án (ứng dụng single-machine, không có backend) — đồ án không cạnh tranh về tính năng/quy mô với các sản phẩm này, mà tập trung chứng minh khả năng tự thiết kế các kỹ thuật CV lõi (head pose, identity verification, fusion engine) ở quy mô một đồ án tốt nghiệp.

---

## 7. Định hướng rút ra cho đồ án

Từ khảo sát mục 5, đồ án xác định rõ ba đóng góp kỹ thuật cụ thể (đối chiếu trực tiếp với hạn chế của dự án tham khảo nêu ở mục 1):

| Hạn chế của bản tham khảo | Cơ sở lý thuyết đồ án áp dụng | Kỹ thuật cài đặt |
|---|---|---|
| So lệch pixel mắt–mũi 2D, không có góc quay thật | Hình học PnP (mục 5.1.1) | `cv2.solvePnP` + 6 điểm landmark MediaPipe FaceMesh |
| Không xác thực danh tính xuyên suốt | Face embedding + cosine similarity (mục 5.2) | facenet-pytorch (InceptionResnetV1) + ngưỡng có biên độ |
| if/elif ưu tiên, bỏ sót đa vi phạm, dao động quanh ngưỡng | Rule-based weighted fusion + hysteresis (mục 5.3) | State machine theo cửa sổ trượt + điểm rủi ro có trọng số + ngưỡng kép |

Các lựa chọn này ưu tiên tính khả thi trong thời gian đồ án (không cần huấn luyện mô hình mới, không cần calibration camera thật, không cần dữ liệu huấn luyện lớn) trong khi vẫn có cơ sở lý thuyết vững chắc và có thể đánh giá định lượng được (mục 3.3 của `KE_HOACH_DO_AN.md`) — sẽ được trình bày chi tiết ở chương Thiết kế hệ thống và Thực nghiệm & Đánh giá của luận văn.

---

## 8. Nguồn tham khảo

1. Schroff, F., Kalenichenko, D., & Philbin, J. (2015). *FaceNet: A Unified Embedding for Face Recognition and Clustering*. CVPR 2015.
2. Deng, J., Guo, J., Yang, J., Xue, N., Kotsia, I., & Zafeiriou, S. (2019). *ArcFace: Additive Angular Margin Loss for Deep Face Recognition*. CVPR 2019, [arXiv:1801.07698](https://arxiv.org/abs/1801.07698).
3. Soukupová, T., & Čech, J. (2016). *Real-Time Eye Blink Detection Using Facial Landmarks*. 21st Computer Vision Winter Workshop.
4. Kartynnik, Y., Ablavatski, A., Grishchenko, I., & Grundmann, M. (2019). *Real-time Facial Surface Geometry from Monocular Video on Mobile GPUs* (MediaPipe Face Mesh, 468 landmarks).
5. Ruiz, N., & Chong, E. (2018). *Fine-Grained Head Pose Estimation Without Keypoints*. CVPR Workshops 2018.
6. Deep learning and machine learning techniques for head pose estimation: a survey. *Artificial Intelligence Review*, Springer Nature, 2024.
7. PyImageSearch — *Eye blink detection with OpenCV, Python, and dlib* (giải thích trực quan công thức EAR).
8. Sensor fusion methods for reducing false alarms in heart rate monitoring. PubMed, 2015.
9. Proctorio — trang sản phẩm chính thức, [proctorio.com](https://proctorio.com), truy cập 2026-07.
10. Honorlock — trang sản phẩm chính thức, [honorlock.com](https://honorlock.com), truy cập 2026-07.
11. `KE_HOACH_DO_AN.md`, `KE_HOACH_4_THANG_THEO_TUAN.md` — tài liệu kế hoạch nội bộ đồ án.
