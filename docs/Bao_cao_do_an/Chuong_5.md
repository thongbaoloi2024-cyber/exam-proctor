Cài đặt
Tổng quan
Chương 4 đã trình bày thiết kế chi tiết của hệ thống giám sát thi được đề xuất, với kiến trúc 3 tầng rõ ràng và các công thức toán học cụ thể. Chương 5 này sẽ trình bày quá trình cài đặt thực tế (implementation) các thành phần được thiết kế, bao gồm lựa chọn công nghệ, cấu trúc code, tích hợp các thư viện, xử lý các trường hợp đặc biệt (edge case), quản lý tài nguyên, và lưu trữ telemetry. Chương này sẽ giúp người đọc hiểu được cách chuyển đổi từ thiết kế lý thuyết sang một ứng dụng thực tế hoạt động được.
5.1 Lựa chọn Công nghệ và Thư viện
5.1.1 Ngôn ngữ lập trình
Dự án chọn sử dụng Python 3.11+ vì những lý do sau: (i) Python có sinh thái thư viện AI/ML mạnh mẽ và trưởng thành (OpenCV, TensorFlow, PyTorch); (ii) Các thư viện được sử dụng (MTCNN, MediaPipe, YOLOv8, FaceNet) đều có bản triển khai Python chính thức; (iii) Tốc độ phát triển nhanh, phù hợp với khuôn khổ thời gian đồ án; (iv) Dễ bảo trì và mở rộng.
5.1.2 Các thư viện chính
opencv-python: Xử lý ảnh, video, các phép biến đổi hình học cơ bản
mediapipe [13]: Trích xuất 468 landmark 3D chi tiết trên khuôn mặt
mtcnn [2]: Phát hiện khuôn mặt và trích xuất 5 điểm landmark sơ bộ
facenet-pytorch: Trích xuất face embedding từ khuôn mặt (sử dụng mô hình InceptionResnetV1 pretrained)
ultralytics (YOLOv8) [21]: Phát hiện vật thể cấm như điện thoại, sách
numpy: Xử lý ma trận, tính toán số học
scipy: Tính toán cosine similarity, các hàm toán học nâng cao
jsonl: Lưu trữ telemetry dưới dạng JSON Lines (mỗi dòng là một sự kiện)
reportlab hoặc python-pptx: Sinh báo cáo PDF/HTML (tùy theo yêu cầu)
5.2 5.2 Cấu trúc Code và Kiến trúc
Dự án được tổ chức theo cấu trúc như sau:
exam-proctor/
├── main.py                 # Entry point chính
├── config/
│   └── config.yaml         # Cấu hình (ngưỡng, trọng số, file path)
├── src/
│   ├── perception/
│   │   ├── face_detector.py        # MTCNN wrapper
│   │   ├── landmark_extractor.py   # MediaPipe wrapper
│   │   ├── object_detector.py      # YOLOv8 wrapper
│   │   └── perception_layer.py     # Kết hợp ba phần trên
│   ├── signals/
│   │   ├── face_presence.py        # Signal 1
│   │   ├── multi_face.py           # Signal 2
│   │   ├── eye_state.py            # Signal 3 (EAR)
│   │   ├── mouth_state.py          # Signal 4
│   │   ├── object_presence.py      # Signal 5
│   │   ├── head_pose.py            # Signal 6 (solvePnP)
│   │   ├── identity_verification.py # Signal 7 (FaceNet)
│   │   └── signal_extractors.py    # Kết hợp 7 signal
│   ├── fusion/
│   │   ├── state_machine.py        # State machine cho mỗi signal
│   │   ├── risk_fusion.py          # Tính risk_score, hysteresis
│   │   └── violation_detector.py   # Quyết định báo động
│   ├── telemetry/
│   │   ├── session_recorder.py     # Ghi lại telemetry vào JSONL
│   │   └── report_generator.py     # Sinh báo cáo PDF/HTML
│   └── utils/
│       ├── camera.py               # Quản lý webcam
│       ├── logger.py               # Ghi log
│       └── helpers.py              # Hàm tiện ích
└── models/
└── (các pretrained model nếu không download từ internet)
5.3 Chi tiết Triển khai Từng Thành phần
5.3.1 Perception Layer
Perception Layer là tầng đầu tiên xử lý từng khung hình. Cấu trúc hoạt động:
class PerceptionLayer:
def __init__(self):
self.face_detector = MTCNNDetector()
self.landmark_extractor = MediaPipeExtractor()
self.object_detector = YOLOv8Detector()

def process_frame(self, frame):
# Phát hiện khuôn mặt + 5 landmark
faces = self.face_detector.detect(frame)

# Trích xuất 468 landmark 3D
face_mesh = self.landmark_extractor.extract(frame)

# Phát hiện vật thể
objects = self.object_detector.detect(frame)

return {
'faces': faces,           # Danh sách bounding box, xác suất
'landmarks_5': face_mesh.get_5_landmarks(),  # 5 điểm từ MTCNN
'landmarks_468': face_mesh.get_468_landmarks(),  # 468 điểm
'objects': objects         # Các vật thể phát hiện được
}
5.3.2 Signal Extractors
Mỗi signal extractor nhận đầu ra từ Perception Layer và tính điểm (0-1) cho tín hiệu đó:
class EyeStateSignal:
def __init__(self, threshold=0.1):
self.threshold = threshold

def compute_ear(self, landmarks):
# Tính Eye Aspect Ratio từ 6 điểm mốc quanh mắt
# EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
# Công thức được áp dụng cho cả hai mắt
left_ear = calculate_ear(landmarks[left_eye_indices])
right_ear = calculate_ear(landmarks[right_eye_indices])
return (left_ear + right_ear) / 2

def extract(self, frame, landmarks):
ear = self.compute_ear(landmarks)
# Signal = 0 nếu EAR cao (mắt mở), 1 nếu EAR thấp (mắt nhắm)
return 1.0 if ear < self.threshold else 0.0
Tương tự, các signal khác (identity verification, head pose, v.v.) cũng có cấu trúc tương tự với một phương thức extract() trả về điểm từ 0-1.
5.3.3 Risk Fusion Engine
Risk Fusion Engine là phần logic quyết định chính:
class RiskFusionEngine:
def __init__(self, weights, threshold_up=0.70, threshold_down=0.50):
self.weights = weights  # w1=0.20, w2=0.02, w3=0.03, ..., w7=0.35
self.threshold_up = threshold_up
self.threshold_down = threshold_down
self.state = 'normal'  # 'normal' hoặc 'alert'

def compute_risk_score(self, signals):
# risk_score = Σ(wi × signali)
risk_score = sum(w * s for w, s in zip(self.weights, signals))
return risk_score

def update_state(self, risk_score):
# Hysteresis: 2 ngưỡng khác nhau
if self.state == 'normal' and risk_score > self.threshold_up:
self.state = 'alert'
elif self.state == 'alert' and risk_score < self.threshold_down:
self.state = 'normal'
return self.state == 'alert'

def process(self, signals):
risk_score = self.compute_risk_score(signals)
is_violation = self.update_state(risk_score)
return {'risk_score': risk_score, 'is_violation': is_violation}
5.4 Xử lý Edge Cases
Trong quá trình triển khai, có một số tình huống đặc biệt cần xử lý:
5.4.1 Không phát hiện khuôn mặt
Khi MTCNN không phát hiện được khuôn mặt (ví dụ thí sinh quay mặt hoàn toàn ra khác, hoặc che khuất khuôn mặt):
if no_face_detected:
# Face Presence signal = 1.0 (bất thường)
face_presence_signal = 1.0
# Các signal khác không thể tính được
eye_state_signal = 0.0  # Coi là bình thường (không phát hiện = không có lỗi)
mouth_state_signal = 0.0
head_pose_signal = 0.0
identity_signal = 0.0  # Hoặc có thể coi là báo động nếu không thể xác thực
5.4.2 Nhiều khuôn mặt trong khung hình
Nếu phát hiện > 1 khuôn mặt:
if num_faces > 1:
multi_face_signal = 1.0  # Báo động
# Tiếp tục xử lý dựa trên khuôn mặt lớn nhất (giả sử đó là thí sinh)
primary_face = get_largest_face(faces)
# Xử lý như bình thường với primary_face
5.4.3 Điều kiện ánh sáng xấu
Nếu ảnh quá tối hoặc quá sáng:
brightness = calculate_brightness(frame)
if brightness < min_brightness or brightness > max_brightness:
# Ghi log cảnh báo về điều kiện ánh sáng
logger.warn(f"Poor lighting condition: {brightness}")
# Tiếp tục xử lý nhưng có thể có độ chính xác thấp hơn
5.5 Lưu trữ Telemetry và Báo cáo
5.5.1 Lưu trữ Telemetry
Telemetry được lưu dưới dạng JSON Lines (JSONL), mỗi dòng là một JSON object đại diện cho một khung hình hoặc một sự kiện:
{"timestamp": "2026-08-12T10:30:45.123Z", "frame_id": 0, "signals": [0.0, 0.0, 0.1, 0.0, 0.0, 0.05, 0.0], "risk_score": 0.018, "state": "normal"}
{"timestamp": "2026-08-12T10:30:45.133Z", "frame_id": 1, "signals": [0.0, 0.0, 0.15, 0.0, 0.0, 0.06, 0.0], "risk_score": 0.022, "state": "normal"}
...
{"timestamp": "2026-08-12T10:35:12.456Z", "frame_id": 300, "signals": [0.0, 0.0, 0.9, 0.0, 0.0, 0.08, 0.0], "risk_score": 0.040, "state": "alert", "violation": "eye_closed_prolonged"}
Khi phát hiện vi phạm (risk_score vượt ngưỡng), hệ thống tự động chụp ảnh từ khung hình hiện tại và lưu vào thư mục snapshots/:
if is_violation:
# Chụp ảnh chứng minh
snapshot_path = f"sessions/{session_id}/snapshots/{frame_id}_{timestamp}.jpg"
cv2.imwrite(snapshot_path, frame)

# Ghi sự kiện vi phạm vào JSONL
violation_event = {
'timestamp': timestamp,
'violation_type': get_violation_type(signals),
'risk_score': risk_score,
'snapshot': snapshot_path,
'contributing_signals': [s for i, s in enumerate(signals) if s > 0.1]
}
write_jsonl(session_jsonl, violation_event)
5.5.2 Sinh Báo cáo
Sau kỳ thi, báo cáo được sinh dựa trên telemetry được lưu:
class ReportGenerator:
def generate_html_report(self, session_id, telemetry_file):
# Đọc telemetry từ JSONL
events = read_jsonl(telemetry_file)

# Tính toán thống kê
violations = [e for e in events if 'violation' in e]
avg_risk = np.mean([e['risk_score'] for e in events])

# Sinh HTML với:
# - Timeline các vi phạm
# - Ảnh chứng minh
# - Biểu đồ risk score theo thời gian
# - Thống kê hành vi

html_content = self.render_template('report.html', {
'violations': violations,
'avg_risk': avg_risk,
'report_time': datetime.now(),
'session_duration': calculate_duration(events)
})

return html_content
5.6 Tối ưu Hiệu suất
5.6.1 Giảm Độ phân giải Ảnh
Để tăng tốc độ xử lý, ảnh từ webcam có thể được resize từ 1280×720 xuống 640×360 trước khi truyền vào các model:
frame = cv2.resize(frame, (640, 360))
5.6.2 Sử dụng GPU
Nếu có GPU (NVIDIA, AMD), các model sẽ tự động sử dụng GPU để tăng tốc độ:
device = 'cuda' if torch.cuda.is_available() else 'cpu'
face_embedding_model = FaceNet(pretrained=True).to(device)
5.6.3 Cache các Mô hình
Tránh tải lại mô hình mỗi lần, thay vào đó cache chúng khi khởi động:
class ModelCache:
_instances = {}

@classmethod
def get_mtcnn(cls):
if 'mtcnn' not in cls._instances:
cls._instances['mtcnn'] = MTCNNDetector()
return cls._instances['mtcnn']
Kết chương
Chương 5 đã trình bày quá trình cài đặt thực tế của hệ thống, từ lựa chọn công nghệ, cấu trúc code, chi tiết triển khai từng thành phần, đến xử lý các edge case và tối ưu hiệu suất. Kiến trúc modular cho phép dễ bảo trì, test từng thành phần độc lập, và mở rộng trong tương lai. Lưu trữ telemetry dưới dạng JSONL cho phép phân tích chi tiết về hành vi của thí sinh và sinh báo cáo toàn diện. Chương 6 tiếp theo sẽ trình bày quá trình thực nghiệm để đánh giá hiệu năng của hệ thống trên bộ test (25 clip ngắn gần 1 tiếng đồng hồ).
