# So sánh kỹ thuật Tuần 4: EyeState / MouthState / Object với bản tham khảo

> Đối chiếu trực tiếp code (`exam-cheating-detection/src/detection/eye_tracking.py`,
> `mouth_detection.py`, `object_detection.py`, `config/config.yaml`) với 3 signal
> đã cài đặt Tuần 4, để quyết định giữ nguyên hay sửa theo hướng nào cho từng
> phần. Đây là so sánh **kỹ thuật/code**, phục vụ chương Thực nghiệm & Đánh giá
> sau này — không copy code từ bản tham khảo, chỉ đối chiếu để rút ra quyết
> định thiết kế.

## 1. Eye — EAR vs "gaze theo lệch pixel"

| | Bản tham khảo (`eye_tracking.py`) | Đồ án (`EyeStateSignal`) |
|---|---|---|
| Landmark mắt | `[33,160,158,133,153,144]` / `[362,385,387,263,373,380]` | Giống hệt tập điểm (đặt tên trái/phải ngược nhau, không ảnh hưởng logic) |
| Công thức EAR | `(A+B)/(2*C)` — đúng công thức Soukupová & Čech | Giống hệt công thức (đây là công thức học thuật chuẩn, không phải "sáng chế riêng" của bản tham khảo nên dùng chung là hợp lệ) |
| **Điều tính EAR dùng để làm gì** | Tính `eye_ratio` nhưng **KHÔNG BAO GIỜ dùng để cảnh báo** — `EYE_ASPECT_RATIO_THRESH=0.3` và `EYE_ASPECT_RATIO_CONSEC_FRAMES=3` được định nghĩa trong `__init__` nhưng **không xuất hiện lần nào** trong `track_eyes()`. `config.yaml` cũng có `blink_threshold: 0.3` — cũng chết, không nơi nào đọc lại giá trị này để so sánh với EAR. | EAR **là cơ chế cảnh báo chính**, có ngưỡng (`ear_threshold=0.21`) + debounce thời gian nhắm mắt liên tục thực sự chạy |
| Cảnh báo thật sự dùng gì | So lệch **pixel tuyệt đối** giữa tâm mắt và mũi (`horiz_diff`), ngưỡng cứng `15` pixel (`gaze_sensitivity: 15` trong config), không chuẩn hoá theo kích thước khung hình hay khoảng cách tới camera | HeadPoseSignal (Tuần 5, `solvePnP`) sẽ đảm nhiệm phần "nhìn lệch hướng" bằng góc thật (độ), không phải pixel thô |

**Kết luận**: EAR trong bản tham khảo là **dead code** — tính ra nhưng không dùng để quyết định gì cả. Cảnh báo mắt thật sự của họ dựa vào ngưỡng pixel cứng (`15px`), phụ thuộc độ phân giải camera đã hardcode sẵn trong `config.yaml` (`video.resolution: [1280,720]`) — đổi webcam/độ phân giải là ngưỡng sai lệch ngay. Đây đúng là hạn chế đã nêu ở `docs/DE_CUONG_CHI_TIET.md` mục 1, giờ xác nhận bằng code thật.

**Quyết định**: **Giữ nguyên** thiết kế `EyeStateSignal` (EAR làm cơ chế cảnh báo thật, không phải biến chết). Landmark index không đổi (trùng bản tham khảo là hợp lý vì đây là bộ điểm EAR chuẩn cộng đồng dùng, đã verify độc lập qua package — không phải copy). **Không** thêm lại kiểu "gaze theo pixel" — phần đó cố ý nhường cho HeadPoseSignal (Tuần 5) làm đúng bằng hình học 3D, đúng định hướng đồ án đã đặt ra từ đầu.

## 2. Mouth — tỉ lệ chuẩn hoá vs khoảng cách tuyệt đối

| | Bản tham khảo (`mouth_detection.py`) | Đồ án (`MouthStateSignal`) |
|---|---|---|
| Landmark môi trên/dưới | `13, 14` | `13, 14` (giống) |
| Landmark khoé miệng | `78` (phải), **`306`** (trái) | `61, 291` |
| Công thức | `mouth_open = lower.y - upper.y` (khoảng cách **tuyệt đối**, toạ độ chuẩn hoá [0,1] nhưng KHÔNG chia cho kích thước mặt) | `ratio = khoảng_cách_dọc / khoảng_cách_ngang_khoé_miệng` (tự chuẩn hoá, bất biến khoảng cách tới camera) |
| Điều kiện kích hoạt | `mouth_open > 0.03 OR mouth_width > 0.2` | `activity_ratio` (tỉ lệ % frame mở trong cửa sổ trượt) `>= ngưỡng` |
| Đơn vị ngưỡng tích luỹ | `movement_threshold: 3` **frame** (không phải giây) — phụ thuộc FPS máy chạy | `activity_window_sec=2.0` giây — không phụ thuộc FPS |

**3 vấn đề cụ thể phát hiện trong code tham khảo**:
1. **Landmark `306` không nằm trong tập `FACE_LANDMARKS_LIPS`** mà package `mediapipe` thực sự expose (đã verify: tập lips xác nhận có `308`, không có `306`) — nhiều khả năng là lỗi gõ nhầm `308`→`306` khi họ chép từ 1 nguồn nào đó, không tự verify lại. Đây chính là rủi ro mà quy tắc "verify landmark qua package cài đặt, không suy đoán" (đã áp dụng cho `EyeStateSignal`/`MouthStateSignal` từ đầu Tuần 4) được thiết kế để tránh.
2. **`mouth_open`/`mouth_width` không chuẩn hoá theo kích thước khuôn mặt** — cùng 1 tư thế mở miệng, ngồi gần camera hơn sẽ ra số lớn hơn (dễ báo động giả), ngồi xa hơn ra số nhỏ hơn (dễ bỏ sót) — thực nghiệm sau này (Tuần 14) khó tái lập nếu khoảng cách ngồi thay đổi giữa các clip test.
3. **Điều kiện `OR mouth_width > 0.2`** — mặt rộng tự nhiên/cười khép miệng cũng có thể vượt `0.2` dù miệng hoàn toàn đóng theo chiều dọc → false positive không liên quan gì đến "đang nói".
4. **Ngưỡng tích luỹ tính bằng SỐ FRAME** (`movement_threshold: 3`), không phải giây — hành vi đổi tuỳ theo FPS xử lý thực tế của máy (máy chậm hơn → ngưỡng "nhanh" hơn tính theo thời gian thực, máy nhanh hơn → ngưỡng "chậm" hơn). `MouthStateSignal` dùng `activity_window_sec` tính bằng giây nên nhất quán bất kể FPS.

**Điểm bản tham khảo làm đúng hướng (dù còn lỗi kỹ thuật ở trên)**: dùng bộ đếm tích luỹ tăng/giảm dần (leaky counter) thay vì đòi hỏi chuỗi liên tục không ngắt — đây chính là hướng đúng mà bản đầu tiên của `MouthStateSignal` (Tuần 4, trước khi sửa) đã thiếu và gây bug "không phát hiện được nói chuyện" (xem commit sửa lỗi trước đó). Bản sửa hiện tại (`activity_ratio` theo cửa sổ trượt thời gian) đạt được đúng mục tiêu đó nhưng bằng cơ chế chuẩn hơn (time-window, không phụ thuộc FPS).

**Quyết định**: **Giữ nguyên** thiết kế hiện tại của `MouthStateSignal` (đã tốt hơn cả 2 phiên bản kia ở cả 2 mặt: chuẩn hoá theo tỉ lệ VÀ time-window không phụ thuộc FPS). Không đổi landmark (61/291 đã verify đúng, hợp lý hơn cặp 78/306 của bản tham khảo).

## 3. Object — throttle theo thời gian, ngưỡng confidence, kích thước ảnh inference

| | Bản tham khảo (`object_detection.py`) | Đồ án (trước khi sửa Tuần 4 lần này) |
|---|---|---|
| Cách throttle | Từ frame-count (`detection_interval` — bản comment cũ) chuyển sang **thời gian** (`max_fps=5` → `time_since_last < 1/max_fps`) | Đã dùng **thời gian** ngay từ đầu (`object_detect_interval_sec`) |
| `min_confidence` | `0.65` (config đã tune) | `0.40` (chọn ban đầu, chưa có cơ sở thực nghiệm) |
| Kích thước ảnh đưa vào YOLO | Resize riêng xuống `320x320` trước khi inference (nhanh hơn, đủ cho vật thể lớn như điện thoại/sách) | Dùng nguyên `resized_bgr` (mặc định rộng 640px từ Perception Layer) — chậm hơn không cần thiết |
| Xử lý lỗi | `try/except` quanh việc gọi model, log lỗi thay vì crash | Không có — 1 lần YOLO lỗi (frame hỏng, hết bộ nhớ...) sẽ làm crash toàn bộ pipeline đang chạy giữa buổi thi |

**Kết luận**: Cách throttle theo thời gian (không phải theo số frame) của đồ án **đã đúng hướng từ đầu** — bản tham khảo tự sửa từ frame-count sang time-based ở phiên bản sau (còn để lại code frame-count cũ dưới dạng comment trong file), tức là họ cũng nhận ra frame-count không ổn (phụ thuộc FPS, giống lỗi ở mục 2). Xác nhận lựa chọn kiến trúc ban đầu của đồ án là hợp lý.

Ba điểm bản tham khảo làm tốt hơn, đáng áp dụng:
1. **`min_confidence` cao hơn (0.65 vs 0.40)** — hợp lý vì báo động giả "phát hiện điện thoại" có hậu quả nghiêm trọng hơn (nghi ngờ oan thí sinh) so với bỏ sót 1 lần; đồ án sẽ **nâng ngưỡng mặc định lên 0.55** (giữa 2 mốc, có ghi chú sẽ tinh chỉnh bằng thực nghiệm Tuần 14 theo đúng tinh thần `KE_HOACH_DO_AN.md` mục 5, không copy nguyên số 0.65 vì chưa có cơ sở thực nghiệm riêng của đồ án để khẳng định đúng y hệt).
2. **Resize nhỏ hơn trước khi đưa vào YOLO** — đồ án sẽ thêm tham số `imgsz` cho `YOLOObjectDetector` (mặc định 320), giảm tải CPU, cho phép rút ngắn `object_detect_interval_sec` mà không quá tải.
3. **Bọc try/except quanh việc gọi detector** — đồ án sẽ thêm ở tầng `PerceptionLayer` (áp dụng đồng nhất cho cả MTCNN/FaceMesh/YOLO, không chỉ riêng object), để 1 detector lỗi ở 1 frame không làm sập cả phiên giám sát đang chạy.

## 4. Tổng kết thay đổi áp dụng sau so sánh

| Thành phần | Hành động |
|---|---|
| `EyeStateSignal` | Giữ nguyên (đã đúng hướng hơn bản tham khảo — EAR là cơ chế thật, không phải biến chết) |
| `MouthStateSignal` | Giữ nguyên (đã đúng hướng hơn cả 2 mặt: chuẩn hoá tỉ lệ + time-window không phụ thuộc FPS) |
| `YOLOObjectDetector` | Thêm `imgsz` (ban đầu 320), nâng `confidence_threshold` mặc định 0.40 → 0.55 |
| `PerceptionLayer` | Thêm try/except an toàn quanh cả 3 detector (MTCNN/FaceMesh/YOLO), không crash cả phiên khi 1 detector lỗi ở 1 frame |

**Cập nhật sau khi test qua webcam thật (cùng tuần)**: `imgsz=320` (áp dụng theo mục 3 ở trên) khiến YOLOv8n bỏ sót điện thoại khi quay mặt lưng vào camera — góc nhìn vốn đã ít đặc trưng phân biệt hơn (không có màn hình/camera trước rõ ràng, và bản thân bộ COCO cũng thiên lệch nhiều ảnh chụp mặt trước điện thoại), hạ độ phân giải trước khi đưa vào model làm mất thêm chi tiết. Trả `imgsz` về 640 (không downscale thêm so với frame Perception Layer đã resize sẵn) — ưu tiên giữ recall thay vì tốc độ, vì đây là hạn chế đang ảnh hưởng trực tiếp tới khả năng phát hiện, còn hiệu năng chưa ghi nhận là vấn đề. Nếu vẫn còn bỏ sót sau khi trả về 640, nhiều khả năng là hạn chế bản thân YOLOv8n pretrained trên COCO (không phải lỗi code) — phương án tiếp theo là thử `yolov8s.pt` (mô hình lớn hơn), đánh giá bằng thực nghiệm Tuần 14, không đoán.
