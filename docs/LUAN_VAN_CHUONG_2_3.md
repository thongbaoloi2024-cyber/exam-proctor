# Chương 2: Cơ sở lý thuyết

> Tuần 8. Viết dựa trên kinh nghiệm CÀI ĐẶT THỰC TẾ (đã chạy, đã verify, đã sửa bug) — không chỉ chép định nghĩa sách vở. Mỗi mục có phần "Áp dụng trong đồ án" trích dẫn trực tiếp code/quyết định thiết kế thật. Đánh số chương tạm (2-3), sẽ sắp xếp lại đúng vị trí ở Tuần 16.

## 2.1. Tổng quan kiến trúc hệ thống

Hệ thống được tổ chức thành 3 tầng xử lý cho mỗi khung hình webcam (chi tiết đầy đủ ở `docs/DIAGRAMS.md`):

1. **Perception Layer** (`src/perception/`): chạy các model thị giác máy tính nền tảng — MTCNN (dò khuôn mặt), MediaPipe FaceLandmarker (468 điểm landmark), YOLOv8 (dò vật thể cấm) — đúng MỘT lần mỗi khung hình, đóng gói kết quả thành `PerceptionResult` dùng chung cho mọi tầng sau.
2. **Signal Extractors** (`src/signals/`): 7 tín hiệu độc lập, mỗi tín hiệu đọc `PerceptionResult` và áp dụng công thức/ngưỡng riêng để ra 1 `SignalResult` (giá trị đo được + cờ vượt ngưỡng + độ tin cậy).
3. **Risk Fusion Engine** (`src/fusion/`, Tuần 9-10, mục 2.7): tổng hợp 7 `SignalResult` thành 1 quyết định cảnh báo thống nhất qua 2 tầng hysteresis lồng nhau.

Ba kỹ thuật ở mục 2.5, 2.6 và 2.7 (PnP head pose, face embedding, Risk Fusion Engine 2 tầng) là đóng góp kỹ thuật mới của đồ án so với hướng tiếp cận đơn giản của dự án tham khảo — xem Chương 3.

## 2.2. Phát hiện khuôn mặt: MTCNN

**Lý thuyết.** MTCNN (Multi-task Cascaded Convolutional Networks — Zhang et al., 2016) phát hiện khuôn mặt qua 3 mạng con xếp tầng chạy trên kim tự tháp đa tỉ lệ (image pyramid) của ảnh đầu vào:
- **P-Net** (Proposal Network): quét nhanh toàn ảnh ở nhiều tỉ lệ, đề xuất một lượng lớn vùng ứng viên có khả năng chứa khuôn mặt.
- **R-Net** (Refine Network): lọc lại các ứng viên từ P-Net, loại bỏ phần lớn false positive.
- **O-Net** (Output Network): tinh chỉnh cuối cùng, đồng thời trả về 5 điểm landmark thô (2 mắt, mũi, 2 khoé miệng).

Việc chạy nhiều mạng con qua nhiều tỉ lệ ảnh giải thích một phát hiện thực nghiệm quan trọng của đồ án (mục 2.2 dưới, và `docs/PERFORMANCE_NOTES.md`): MTCNN — dù thường được xem là "nhẹ" — lại là bottleneck hiệu năng lớn nhất trong toàn bộ pipeline (~29ms/frame, 67% tổng chi phí tính toán), nặng hơn cả YOLOv8.

**Áp dụng trong đồ án.** MTCNN được dùng ở **hai vai trò tách biệt** với hai instance riêng:
1. `MTCNNFaceDetector` (`src/perception/face_detector.py`, dùng trong Perception Layer): chỉ lấy bounding box + confidence, `keep_all=True` để trả về TẤT CẢ khuôn mặt (không chỉ 1) — phục vụ `FacePresenceSignal` (đếm thời gian vắng mặt liên tục) và `MultiFaceSignal` (đếm số khuôn mặt độ tin cậy cao).
2. `FaceEmbedder` (`src/perception/face_embedder.py`, dùng riêng cho `IdentitySignal`, Tuần 6): dùng MTCNN với `keep_all=False, select_largest=True` (tham số mặc định thật của thư viện `facenet-pytorch`, đã xác minh qua `inspect.signature()` chứ không giả định) để tự động chọn khuôn mặt LỚN NHẤT khi có nhiều người, cho ra ảnh khuôn mặt đã align+crop đúng chuẩn 160×160 để đưa vào mạng embedding (mục 2.6) — khác với vai trò 1, ở đây không chỉ cần bbox mà cần ảnh đã căn chỉnh đúng góc/tỉ lệ theo chuẩn huấn luyện của InceptionResnetV1.

## 2.3. Landmark khuôn mặt & Eye Aspect Ratio: MediaPipe FaceMesh

**Lý thuyết.** MediaPipe Face Landmarker (Kartynnik et al., 2019) là một mạng neural hồi quy trực tiếp 468 điểm 3D xấp xỉ bề mặt khuôn mặt từ MỘT ảnh camera đơn (không cần cảm biến depth), chạy real-time. Một phát hiện kỹ thuật đáng chú ý khi cài đặt: bản `mediapipe` cài trong dự án (0.10.14 trên Windows) **không còn API cũ** `mp.solutions.face_mesh.FaceMesh` mà chỉ còn Tasks API mới (`mediapipe.tasks.python.vision.FaceLandmarker`), đòi hỏi tải riêng 1 file model `.task` (không bundle sẵn trong gói pip) — một chi tiết triển khai thực tế không có trong tài liệu lý thuyết sách vở, chỉ phát hiện được khi thử cài đặt thật (`src/perception/face_mesh_detector.py`).

**Eye Aspect Ratio (EAR)** (Soukupová & Čech, 2016) là một đại lượng hình học đo độ mở của mắt từ 6 điểm landmark quanh viền mắt (2 khoé, 2 điểm mí trên, 2 điểm mí dưới), đặt tên P1..P6 theo thứ tự quanh viền mắt:

```
EAR = (‖P2−P6‖ + ‖P3−P5‖) / (2 · ‖P1−P4‖)
```

Tử số đo khoảng cách dọc (mí trên–mí dưới, 2 cặp điểm), mẫu số đo khoảng cách ngang (2 khoé mắt) để chuẩn hoá theo kích thước mắt — mắt mở có EAR ~0.25-0.35, mắt nhắm gần 0.

**Áp dụng trong đồ án — 2 bài học kỹ thuật thực tế đáng chú ý:**

1. **Xác minh chỉ số landmark thay vì suy đoán.** Bộ 468 điểm của MediaPipe không có tài liệu chính thức nào liệt kê rõ "điểm nào là khoé mắt trái/phải" ở dạng dễ tra cứu. Thay vì chép số từ 1 nguồn không kiểm chứng, đồ án dùng chính API `FaceLandmarksConnections` mà package `mediapipe` cài đặt expose để lấy đúng tập điểm viền mắt/môi thật (`FACE_LANDMARKS_LEFT_EYE`, `RIGHT_EYE`, `LIPS`), sau đó chọn 6 điểm P1-P6 chuẩn Soukupová & Čech từ tập đó. Khi đối chiếu với code của dự án tham khảo (`docs/SO_SANH_KY_THUAT_TUAN4.md`), phát hiện họ dùng 1 chỉ số môi (`306`) **không tồn tại trong tập LIPS thật** — một minh chứng cụ thể cho rủi ro chép số không kiểm chứng.

2. **Bug thực tế: méo tỉ lệ do trộn toạ độ chuẩn hoá không đồng nhất.** Bản cài đặt EAR đầu tiên tính khoảng cách Euclidean trực tiếp trên toạ độ CHUẨN HOÁ của MediaPipe (x chia cho chiều rộng ảnh, y chia cho chiều cao ảnh — 2 tỉ lệ khác nhau khi ảnh không vuông). Khi test qua webcam thật (khung hình 640×480, không vuông), lỗi này khiến EAR đo được luôn cao hơn giá trị thật đúng hệ số `width/height ≈ 1.33`, nên mắt nhắm thật vẫn không tụt xuống dưới ngưỡng — bug không hề bị unit test tự động phát hiện (vì test cũng vô tình dựng dữ liệu theo cùng kiểu sai), chỉ lộ ra khi có dữ liệu khuôn mặt thật. Đã sửa bằng cách quy đổi landmark sang toạ độ PIXEL thật (`FaceLandmarks.to_pixel()`) trước khi tính khoảng cách. Đây là minh chứng thực nghiệm cho nguyên lý: **test tổng hợp (synthetic) chỉ xác nhận công thức tự nhất quán, không xác nhận đúng với hình học thật** — cần dữ liệu thật để phát hiện lớp lỗi này.

Công thức tương tự (tỉ lệ khoảng cách dọc/ngang, tự thiết kế không sao chép, đã chuẩn hoá đúng bằng pixel) cũng được dùng cho `MouthStateSignal` đo độ mở miệng.

## 2.4. Phát hiện vật thể: YOLOv8

**Lý thuyết.** YOLO (You Only Look Once) là họ mô hình phát hiện vật thể một giai đoạn (one-stage detector): thay vì đề xuất vùng ứng viên rồi phân loại riêng (kiểu R-CNN 2 giai đoạn), YOLO dự đoán đồng thời vị trí bounding box và lớp vật thể trong 1 lượt truyền xuôi qua mạng, đánh đổi 1 phần độ chính xác lấy tốc độ. YOLOv8 (Ultralytics, 2023) là phiên bản mới nhất trong họ này lúc thực hiện đồ án, kiến trúc anchor-free, huấn luyện sẵn trên bộ dữ liệu COCO (80 lớp vật thể phổ biến).

**Áp dụng trong đồ án.** Model `yolov8n.pt` (biến thể nhỏ nhất, ưu tiên tốc độ) được giới hạn chỉ giữ lại 2 lớp: `cell phone` (id 67) và `book` (id 73) — 2 id này được xác minh trực tiếp qua `model.names` của model đã tải (không đoán, vì bộ COCO gốc 90 lớp có id không liên tục, còn bộ 80 lớp mà Ultralytics dùng đã đánh số lại liên tục). Hai bài học thực nghiệm quan trọng, cả hai đều rút ra khi **đối chiếu với dự án tham khảo** (`docs/SO_SANH_KY_THUAT_TUAN4.md`):

1. **Throttle theo thời gian, không phải theo số frame.** YOLO tốn tài nguyên hơn hẳn MTCNN/FaceMesh, nên chỉ chạy lại mỗi `object_detect_interval_sec` giây (không phải mỗi frame) — dự án tham khảo ban đầu cũng dùng cách đếm frame (`detection_interval` số frame) nhưng sau tự sửa sang cách tính theo giây (đoạn code cũ bị comment lại trong file của họ), xác nhận độc lập rằng cách tiếp cận theo thời gian của đồ án là đúng hướng ngay từ đầu.

2. **Đánh đổi giữa tốc độ và độ nhạy phát hiện (recall).** Khi test qua webcam thật, mô hình bỏ sót điện thoại khi quay MẶT LƯNG vào camera (ít đặc trưng phân biệt hơn mặt trước có màn hình sáng — bản thân bộ COCO cũng thiên lệch nhiều ảnh chụp mặt trước). Đồ án từng hạ độ phân giải ảnh đưa vào model (`imgsz`) từ 640 xuống 320 để tăng tốc (theo kinh nghiệm dự án tham khảo), nhưng phải hoàn lại về 640 sau khi phát hiện việc downscale làm mất thêm chi tiết vốn đã ít ở góc nhìn khó — một ví dụ cụ thể cho thấy tối ưu tốc độ không kiểm chứng bằng dữ liệu thật có thể âm thầm làm giảm chất lượng phát hiện.

## 2.5. Ước lượng góc quay đầu bằng PnP (Perspective-n-Point)

**Lý thuyết.** Bài toán PnP là bài toán kinh điển trong thị giác máy tính: cho một tập điểm 3D đã biết toạ độ trong không gian vật thể (model space) và toạ độ 2D tương ứng của chúng trên ảnh (sau khi chiếu qua 1 camera), tìm phép biến đổi cứng (rotation + translation) mô tả camera đang nhìn vật thể đó từ góc nào. `cv2.solvePnP` giải bài toán này bằng cách tối thiểu hoá sai số tái chiếu (reprojection error) giữa điểm 3D chiếu qua (R, t, camera matrix) ước lượng và điểm 2D quan sát thật.

Với khuôn mặt, quy trình 4 bước: (1) chọn 6 điểm landmark 2D đặc trưng (đỉnh mũi, cằm, 2 khoé mắt, 2 khoé miệng); (2) ánh xạ với 1 mô hình khuôn mặt 3D xấp xỉ chuẩn (không cần đo thật từng người — dùng bộ số liệu kinh điển của Satya Mallick/LearnOpenCV, tái sử dụng rộng rãi trong cộng đồng); (3) ước lượng ma trận nội tại camera (camera matrix) xấp xỉ theo độ phân giải ảnh khi không có calibration thật (focal length ≈ chiều rộng ảnh); (4) giải PnP ra rotation vector, dùng công thức Rodrigues chuyển sang ma trận xoay, rồi phân rã thành 3 góc Euler yaw (quay trái/phải)/pitch (cúi/ngẩng)/roll (nghiêng đầu).

**Vì sao chọn PnP thay vì học sâu**: các phương pháp học sâu dự đoán góc quay đầu trực tiếp từ ảnh (landmark-free, VD Ruiz & Chong 2018) có độ chính xác cao hơn trên benchmark chuẩn nhưng cần dữ liệu huấn luyện gán nhãn góc thật — không khả thi trong ràng buộc thời gian đồ án (không có dữ liệu huấn luyện). PnP không cần huấn luyện, có ý nghĩa hình học tường minh (góc thật theo độ, không phải điểm số tương đối), và tái sử dụng landmark đã có sẵn từ MediaPipe FaceMesh (không phát sinh thêm chi phí dò landmark riêng).

**Áp dụng trong đồ án — kiểm chứng bằng thực nghiệm số thay vì tin vào trí nhớ công thức.** Công thức phân rã ma trận xoay thành góc Euler dễ nhầm dấu/thứ tự trục nếu chỉ nhớ lại từ tài liệu. Đồ án kiểm chứng theo 2 bước: (1) dựng ma trận xoay từ góc biết trước (VD yaw thuần 30°), decode lại bằng công thức, xác nhận khớp; (2) kiểm chứng TOÀN BỘ pipeline end-to-end bằng cách chiếu 6 điểm mô hình 3D chuẩn qua 1 phép quay đã biết trước ra toạ độ 2D, đưa ngược vào `solve_head_pose()`, xác nhận góc khôi phục khớp góc ban đầu (sai số <0.5° trên dữ liệu tổng hợp không nhiễu — `tests/test_head_pose_math.py`). Đây là cách kiểm chứng chặt nhất có thể làm mà không cần webcam/khuôn mặt thật — dù vậy, **việc dấu góc (yaw dương = quay trái hay phải) có khớp trực giác người dùng thật hay không vẫn cần xác nhận bằng webcam thật** (phụ thuộc việc frame webcam có bị lật gương hay không, một yếu tố vật lý không suy ra được từ toán học thuần tuý) — giới hạn đã ghi nhận rõ và còn đang chờ xác nhận (`docs/HEAD_POSE_NOTES.md` mục 6.1).

## 2.6. Xác thực danh tính: Face Embedding & Cosine Similarity

**Lý thuyết.** Thay vì phân loại khuôn mặt vào 1 tập lớp cố định, các hệ thống face verification hiện đại học một phép ánh xạ (embedding) từ ảnh khuôn mặt sang 1 vector số chiều thấp (thường 128-512 chiều), sao cho khoảng cách giữa 2 embedding của cùng 1 người nhỏ, của 2 người khác nhau lớn. **FaceNet** (Schroff, Kalenichenko & Philbin, 2015) đặt nền móng cho hướng này bằng **triplet loss**: huấn luyện mạng sao cho với 3 ảnh (anchor, positive — cùng người với anchor, negative — khác người), khoảng cách embedding(anchor, positive) nhỏ hơn khoảng cách embedding(anchor, negative) một biên độ (margin) nhất định. `InceptionResnetV1` huấn luyện trên bộ dữ liệu VGGFace2 (dùng qua thư viện `facenet-pytorch`) là một triển khai phổ biến của hướng tiếp cận này, cho ra embedding 512 chiều.

Việc so khớp 2 embedding dùng **cosine similarity** — tích vô hướng chuẩn hoá theo độ dài 2 vector, giá trị trong [-1, 1], càng gần 1 càng giống nhau:

```
cos_sim(a, b) = (a · b) / (‖a‖ · ‖b‖)
```

**Áp dụng trong đồ án — thiết kế 2 giai đoạn + ngưỡng có biên độ.** Đây là kỹ thuật hoàn toàn mới so với dự án tham khảo (vốn chỉ đếm số khuôn mặt, không xác minh danh tính). Kiến trúc gồm: (1) **enrollment** 1 lần lúc bắt đầu phiên — lấy trung bình embedding từ 3-5 frame đầu làm embedding tham chiếu (ổn định hơn 1 frame đơn lẻ); (2) **re-verification định kỳ** (mỗi 30s, không phải mỗi frame — vì trích embedding tốn ~28ms/lần, đắt hơn hẳn các phép tính hình học của signal khác) — so cosine similarity với embedding tham chiếu.

Ngưỡng quyết định KHÔNG phải 1 hằng số nhị phân đơn giản mà **có biên độ 2 mức** (`cosine_threshold_warn=0.60`, `cosine_threshold_alert=0.45`) cộng thêm **debounce 2 lần fail liên tiếp** qua các chu kỳ 30s mới kết luận `IDENTITY_MISMATCH` — thiết kế này xuất phát từ hạn chế đã biết trước của phương pháp: cosine similarity nhạy với thay đổi ánh sáng/góc nghiêng dù không đổi người, nên cần vùng đệm để tránh báo động giả (chi tiết đầy đủ, gồm cả các giới hạn chưa giải quyết được như không chống giả mạo ảnh/video: `docs/IDENTITY_NOTES.md`).

## 2.7. Kết hợp đa tín hiệu: Hysteresis 2 cấp & Risk Score có trọng số

**Lý thuyết.** Bài toán kết hợp nhiều nguồn tín hiệu không chắc chắn thành 1 quyết định nhị phân là bài toán kinh điển trong lý thuyết điều khiển và fusion cảm biến. Hai công cụ được dùng ở đây:

1. **Hysteresis (Schmitt trigger)** — kỹ thuật kinh điển trong mạch điện tử/điều khiển tự động để chống dao động (chattering) khi 1 tín hiệu dao động quanh 1 ngưỡng duy nhất: thay vì 1 ngưỡng, dùng 2 ngưỡng khác nhau cho chiều vào và chiều ra (ngưỡng vào cao hơn ngưỡng ra), tạo 1 "vùng đệm" mà tín hiệu phải vượt qua hẳn mới đổi trạng thái, và phải tụt hẳn xuống mới đổi ngược lại.
2. **Weighted decision fusion** — kết hợp nhiều nguồn bằng tổng có trọng số (thay vì luật ưu tiên if/elif) là cách tiếp cận phổ biến khi các nguồn có độ tin cậy/mức độ nghiêm trọng khác nhau và có thể xảy ra đồng thời — mỗi nguồn đóng góp độc lập vào 1 điểm số chung thay vì "thắng-thua" loại trừ lẫn nhau.

**Áp dụng trong đồ án — 2 tầng hysteresis lồng nhau, độc lập với nhau:**

**Tầng 1 — per-signal state machine (Tuần 9, `src/fusion/signal_state_machine.py`, `tracker.py`).** Mỗi trong 7 signal có 1 state machine RIÊNG với 3 trạng thái `NORMAL → SUSPICIOUS → ALERT`, chuyển trạng thái dựa trên `exceed_ratio` — tỉ lệ % frame vượt ngưỡng thô trong 1 cửa sổ trượt theo thời gian (mặc định 4 giây) — chứ không dựa trên 1 frame đơn lẻ. Bản thân state machine này cũng dùng hysteresis 2 mức (`r_enter_susp=0.3 / r_exit_susp=0.15` và `r_enter_alert=0.6 / r_exit_alert=0.4`), và ràng buộc thiết kế quan trọng: **ALERT chỉ thoát được qua SUSPICIOUS, không nhảy thẳng về NORMAL** — tránh 1 tín hiệu đang báo động nghiêm trọng bị xoá sạch chỉ vì 1 khung hình tụt ngưỡng thoáng qua. Điểm khác biệt cốt lõi so với bản tham khảo (mục 3.2): 7 state machine này hoàn toàn ĐỘC LẬP với nhau — không có nhánh if/elif nào so sánh/loại trừ giữa các signal — nên nhiều signal hoàn toàn có thể cùng ở ALERT đồng thời, đúng thực tế 1 người có thể vừa quay đầu ra ngoài vừa nói chuyện cùng lúc.

**Tầng 2 — risk score có trọng số + hysteresis phiên (Tuần 10, `src/fusion/engine.py`, `session.py`).** Sau khi có trạng thái (quy đổi số: NORMAL=0, SUSPICIOUS=1, ALERT=2) của cả 7 signal, tính:

```
risk_score = Σ_i ( weight_i × state_value_i )
```

rồi áp 1 lớp hysteresis THỨ HAI, độc lập với hysteresis nội bộ từng signal ở tầng 1, nhưng lần này tác động trực tiếp lên `risk_score` tức thời (không cần cửa sổ trượt riêng — vì `risk_score` đã LÀ tổng hợp của các state machine vốn đã ổn định qua cửa sổ trượt của chính chúng): `SESSION_NORMAL → SESSION_ALERT` khi `risk_score ≥ T_enter`, chỉ thoát về `SESSION_NORMAL` khi `risk_score ≤ T_exit < T_enter`. `ViolationEvent` (đúng schema `docs/DATA_SCHEMAS.md` mục 3, gồm `contributing_signals` là MẢNG ghi lại TẤT CẢ signal đang SUSPICIOUS/ALERT — không chỉ 1 loại vi phạm/frame như bản tham khảo) chỉ sinh ra tại **rising edge** (thời điểm `risk_score` vừa vượt `T_enter`), tránh log bị ngập bởi cùng 1 vi phạm kéo dài.

**Bộ trọng số khởi tạo và căn cứ lựa chọn** (`config/fusion.yaml`, chủ quan ban đầu — sẽ tinh chỉnh bằng số liệu thực nghiệm Precision/Recall ở Tuần 14, không phải số liệu cuối cùng):

| Signal | Weight | Căn cứ |
|---|---|---|
| `IDENTITY` | 3.0 | Thi hộ — vi phạm nghiêm trọng nhất, bằng chứng trực tiếp (embedding không khớp), khó có cách giải thích vô hại |
| `OBJECT_PRESENCE` | 2.5 | Phát hiện điện thoại/tài liệu — bằng chứng cụ thể, khó biện minh bằng hành vi vô hại |
| `FACE_PRESENCE` | 2.0 | Vắng mặt khỏi khung hình — nghiêm trọng nhưng có thể có lý do chính đáng (ngồi lệch camera) |
| `MULTI_FACE` | 2.0 | Xuất hiện người thứ 2 — nghiêm trọng nhưng cần phân biệt với người đi ngang qua |
| `EYE_STATE` | 1.0 | Nhắm mắt/nhìn lệch — dễ nhầm với suy nghĩ/mỏi mắt, cần cộng dồn với tín hiệu khác mới đủ tin cậy |
| `MOUTH_STATE` | 1.0 | Nói chuyện — dễ nhầm với lẩm bẩm khi làm bài, cần cộng dồn |
| `HEAD_POSE` | 1.0 | Quay đầu — dễ nhầm với nhìn đồng hồ/suy nghĩ, cần cộng dồn |

`T_enter=5.0`, `T_exit=2.5` (vùng đệm 50%) được chọn sao cho `OBJECT_PRESENCE` hoặc `IDENTITY` MỘT MÌNH ở ALERT đã đủ để cảnh báo ngay (`2.5×2=5.0`, `3×2=6.0`), trong khi `FACE_PRESENCE`/`MULTI_FACE` một mình ở ALERT (`2×2=4.0`) CHƯA đủ — cần thêm ít nhất 1 tín hiệu phụ mới vượt ngưỡng; 3 tín hiệu hành vi có độ mơ hồ cao (`EYE_STATE`/`MOUTH_STATE`/`HEAD_POSE`) một mình ở ALERT (`1×2=2.0`) càng cần nhiều tín hiệu cộng dồn hơn nữa — đúng chủ đích thiết kế: tín hiệu càng dễ có cách giải thích vô hại thì càng cần nhiều bằng chứng đồng thời mới đủ để cảnh báo.

**Ngưỡng phân loại mức độ nghiêm trọng (`severity`).** Mỗi `ViolationEvent` sinh ra còn được gắn 1 trong 3 mức `LOW`/`MEDIUM`/`HIGH`, suy trực tiếp từ `risk_score` tại thời điểm sinh event (`RiskFusionEngine._severity()`, `src/fusion/engine.py`):

```
severity = HIGH    nếu risk_score ≥ severity_high_min   (= 10.0, mặc định 2×T_enter)
         = MEDIUM   nếu risk_score ≥ severity_medium_min (= 5.0, mặc định = T_enter)
         = LOW      còn lại
```

Vì `ViolationEvent` chỉ sinh ra khi `risk_score ≥ T_enter`, trong thực tế `severity` không bao giờ là `LOW` — mức thấp nhất quan sát được luôn là `MEDIUM` (đúng lúc `risk_score` vừa vượt `T_enter`). `HIGH` đặt ở `2×T_enter=10.0` — mốc tương ứng với 1 tín hiệu trọng số cao đang ALERT CỘNG THÊM ít nhất 1-2 tín hiệu phụ khác cũng đang SUSPICIOUS/ALERT cùng lúc (VD `IDENTITY` ALERT = 6.0 cộng thêm `HEAD_POSE` SUSPICIOUS = 1.0 và `EYE_STATE` SUSPICIOUS = 1.0 vẫn chưa đủ 10.0 — cần nhiều bằng chứng cộng dồn thật sự, không phải 1 tín hiệu đơn lẻ dù nặng đến đâu). Công thức mặc định này được đặt DUY NHẤT tại `resolve_severity_thresholds()` (`src/fusion/config.py`) và dùng chung giữa `RiskFusionEngine` (quyết định severity thật lúc chạy) và `src/reporting/report_generator.py` (tô vùng severity trên biểu đồ risk score) — tránh đúng lỗi "severity map lệch giữa 2 module" mà lẽ ra sẽ phát sinh nếu mỗi nơi tự tính lại công thức mặc định riêng.

**Giới hạn cần ghi nhận trung thực**: thiết kế 2 tầng này giải quyết đúng vấn đề "kết hợp nhiều vi phạm đồng thời thay vì if/elif loại trừ" (mục 3.2), nhưng KHÔNG giải quyết vấn đề đã ghi ở `docs/KET_QUA_DEMO_TUAN8.md` mục 2.1 (EYE_STATE báo nhầm khi đầu quay rất nhiều, cả 2 mắt cùng méo phối cảnh) theo đúng hướng ban đầu dự tính — hướng đó cần HEAD_POSE làm GIẢM ĐỘ TIN CẬY của EYE_STATE một cách CÓ ĐIỀU KIỆN (cross-signal confidence adjustment), trong khi risk score ở đây chỉ CỘNG các trạng thái độc lập lại, không có cơ chế 1 signal điều chỉnh cách tính của signal khác. Nếu đầu quay nhiều khiến cả EYE_STATE lẫn HEAD_POSE cùng báo ALERT giả, risk score vẫn cộng dồn cả 2 như bình thường — hạn chế này để lại cho Tuần 14 (thực nghiệm) đánh giá mức độ ảnh hưởng thực tế, chưa vá thêm ở tầng fusion để tránh làm phức tạp hoá thiết kế khi chưa có số liệu chứng minh cần thiết.

---

# Chương 3: Khảo sát hệ thống liên quan

## 3.1. Dự án tham khảo: exam-cheating-detection

Dự án tham khảo (`AarambhDevHub/AarambhTech`, 2025, giấy phép MIT) là một script giám sát cục bộ đơn máy, dùng OpenCV + MediaPipe + facenet-pytorch (chỉ dùng MTCNN, không dùng phần embedding) + YOLOv8 để phát hiện: vắng mặt khuôn mặt, nhiều khuôn mặt, vật thể cấm, chuyển động mắt/miệng, âm thanh bất thường.

**Vai trò trong đồ án**: chỉ dùng làm tài liệu tham khảo/đối chứng (baseline) để so sánh — không copy code. Việc dùng chung các thư viện nền (OpenCV, MediaPipe, facenet-pytorch, YOLOv8) là bình thường trong mọi đồ án CV (không ai tự viết lại MTCNN hay huấn luyện lại YOLO từ đầu ở cấp đồ án cử nhân/kỹ sư); phần thực sự "của đồ án" là kiến trúc pipeline, công thức trích xuất tín hiệu, thuật toán kết hợp đa tín hiệu, và 2 kỹ thuật mới (Chương 2 mục 2.5, 2.6).

## 3.2. So sánh kỹ thuật chi tiết với bản tham khảo

Khác với đề cương Tuần 1 (chỉ khảo sát qua README/mô tả dự án), đến Tuần 4 đồ án đã **đọc trực tiếp mã nguồn** của dự án tham khảo (`src/detection/eye_tracking.py`, `mouth_detection.py`, `object_detection.py`, `config/config.yaml`) để so sánh ở mức triển khai cụ thể, không chỉ ở mức ý tưởng (toàn bộ chi tiết: `docs/SO_SANH_KY_THUAT_TUAN4.md`). Các phát hiện chính:

| Khía cạnh | Dự án tham khảo | Đồ án | Nhận xét |
|---|---|---|---|
| Phát hiện mắt nhắm | Tính EAR nhưng **không dùng để cảnh báo** (dead code) — cảnh báo thật dựa vào lệch pixel tuyệt đối giữa tâm mắt và mũi, ngưỡng cứng 15px | EAR là cơ chế cảnh báo THẬT, có debounce thời gian | Đồ án lấp đúng khoảng trống: EAR tính ra nhưng bị bỏ phí ở bản gốc |
| Hướng nhìn (gaze) | Lệch pixel 2D thô, không chuẩn hoá theo độ phân giải/khoảng cách camera, không có chiều sâu | Góc PnP thật (yaw/pitch, độ), bất biến với độ phân giải | Đúng trọng tâm "kỹ thuật mới" của đồ án (Chương 2.5) |
| Độ mở miệng | Khoảng cách TUYỆT ĐỐI (không chuẩn hoá theo kích thước mặt); 1 trong 2 landmark khoé miệng dùng (`306`) không tồn tại trong tập landmark môi thật của MediaPipe; ngưỡng tích luỹ tính bằng SỐ FRAME (phụ thuộc FPS máy chạy) | Tỉ lệ dọc/ngang tự chuẩn hoá; landmark verify qua API package thật; ngưỡng tích luỹ tính bằng GIÂY (không phụ thuộc FPS) | 3 lỗi kỹ thuật cụ thể ở bản gốc, đều đã tránh được bằng kỷ luật "verify trước khi dùng" |
| Phát hiện vật thể | `min_confidence=0.65`, throttle theo thời gian (tự sửa từ đếm frame), resize ảnh trước inference | `min_confidence=0.55` (đã điều chỉnh theo hướng của bản gốc), throttle theo thời gian từ đầu, không resize thêm (đã thử rồi hoàn lại — mục 2.4) | Đồ án học được 1 vài lựa chọn tốt từ bản gốc, không phải mọi thứ tự thiết kế đều tốt hơn |
| Xác thực danh tính | Không có | `IdentitySignal` (Chương 2.6) | Khoảng trống lớn nhất — hoàn toàn không có ở bản gốc |
| Kết hợp đa tín hiệu | if/elif có thứ tự ưu tiên, chỉ ghi 1 loại vi phạm/frame | State machine độc lập/tín hiệu (Tuần 9) + risk score có trọng số + hysteresis phiên (Tuần 10) — mục 2.7 | Đã cài đặt; nhiều signal có thể cùng ALERT đồng thời, `ViolationEvent.contributing_signals` ghi lại TẤT CẢ, không chỉ 1 |
| Xử lý lỗi | try/except quanh mọi detector, không crash khi lỗi | Đã áp dụng tương tự (`PerceptionLayer._safe_call`) sau khi đối chiếu | Học theo điểm mạnh về độ bền vững của bản gốc |

**Nhận xét chung**: việc so sánh ở mức mã nguồn (không chỉ mức tài liệu) cho kết quả khách quan hơn — một số điểm đồ án ban đầu cho là "chắc chắn tốt hơn" hoá ra cần điều chỉnh sau khi đối chiếu (ngưỡng confidence vật thể), và một số điểm bản gốc tưởng như đã làm (EAR) hoá ra chỉ là mã chết không hoạt động.

## 3.3. Sản phẩm thương mại (bối cảnh ứng dụng)

Trên thị trường có nhiều nền tảng giám sát thi trực tuyến quy mô lớn. **Proctorio** hoạt động hoàn toàn tự động (không cần giám thị người), dùng phân tích hành vi AI qua tiện ích mở rộng trình duyệt, có hệ thống "Suspicion Score" giúp giảng viên ưu tiên phiên cần xem lại. **Honorlock** theo hướng lai: AI giám sát và phát hiện sơ bộ, chỉ chuyển cho giám thị người khi có dấu hiệu nghi vấn, có cơ chế điều chỉnh mức độ giám sát thích ứng để giảm báo động giả. Cả hai đều là hệ thống client-server đa người dùng quy mô lớn — khác biệt căn bản với phạm vi đồ án (ứng dụng single-machine). Đồ án không cạnh tranh về tính năng/quy mô với các sản phẩm này, mà tập trung chứng minh khả năng tự thiết kế các kỹ thuật CV lõi ở quy mô đồ án tốt nghiệp.

## 3.4. Định hướng đóng góp của đồ án

Tổng hợp từ Chương 2 và mục 3.2, ba đóng góp kỹ thuật cụ thể của đồ án so với dự án tham khảo:

1. **Head Pose Estimation bằng PnP** (Chương 2.5) — thay lệch pixel 2D thô bằng góc quay đầu thật có cơ sở hình học 3D.
2. **Identity Verification bằng face embedding** (Chương 2.6) — khả năng hoàn toàn không có ở bản gốc, phát hiện thi hộ giữa chừng.
3. **Risk Fusion Engine 2 tầng** (Chương 2.7, Tuần 9-10) — thay if/elif ưu tiên bằng state machine độc lập/tín hiệu + risk score có trọng số + hysteresis 2 cấp (per-signal và phiên), cho phép nhiều vi phạm được ghi nhận đồng thời.

Ngoài 3 đóng góp có chủ đích này, quá trình cài đặt (Tuần 3-7) còn phát hiện và sửa một số hạn chế kỹ thuật cụ thể của cách tiếp cận đơn giản (mục 3.2) — bản thân các phát hiện này (không chỉ kết quả cuối) là một phần giá trị khảo sát của đồ án, sẽ dùng làm chất liệu cho chương Thực nghiệm & Đánh giá (Tuần 14).
