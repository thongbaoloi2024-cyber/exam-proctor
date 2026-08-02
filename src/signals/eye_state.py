"""EyeStateSignal — Eye Aspect Ratio (EAR) tính từ landmark MediaPipe FaceMesh.

Công thức EAR (Soukupová & Čech, 2016 — xem docs/DE_CUONG_CHI_TIET.md mục
5.1 và nguồn tham khảo mục 8) áp dụng riêng cho từng mắt bằng 6 điểm:

    EAR = (||P2-P6|| + ||P3-P5||) / (2 * ||P1-P4||)

6 chỉ số landmark P1..P6 của mỗi mắt được LẤY TỪ chính tập hợp điểm viền mắt
mà package `mediapipe` expose qua `FaceLandmarksConnections.FACE_LANDMARKS_
LEFT_EYE/RIGHT_EYE` (đã xác minh trực tiếp trong venv, không đoán số).

Đã đối chiếu trực tiếp với `eye_tracking.py` của dự án tham khảo (xem
docs/SO_SANH_KY_THUAT_TUAN4.md mục 1): họ dùng CÙNG công thức EAR và CÙNG bộ
landmark (không có gì lạ — đây là công thức học thuật chuẩn, không phải tài
sản riêng của họ), nhưng EAR ở đó là **dead code**: tính ra `eye_ratio` rồi
không dùng để cảnh báo gì cả (`EYE_ASPECT_RATIO_THRESH`/`blink_threshold`
định nghĩa trong config nhưng không nơi nào đọc lại). Cảnh báo mắt thật của
họ dựa vào lệch PIXEL tuyệt đối giữa tâm mắt và mũi (ngưỡng cứng 15px,
không chuẩn hoá theo độ phân giải/khoảng cách camera). Ở đây, EAR + debounce
thời gian (`min_closed_duration_sec`) là cơ chế cảnh báo THẬT SỰ chạy —
phần tự thiết kế của đồ án là ngưỡng và cách xử lý theo thời gian, không
phải công thức EAR (công thức là chung, verify riêng qua package đã cài).

Lưu ý phạm vi: EAR đo ĐỘ MỞ mắt (nhắm/mở), KHÔNG đo hướng nhìn (gaze
direction). Phát hiện "nhìn lệch ra ngoài màn hình" theo góc đầy đủ dựa vào
HeadPoseSignal (Tuần 5, thay thế đúng phần lệch-pixel thô của bản tham khảo)
— EYE_STATE ở đây chỉ bắt các trường hợp mắt nhắm bất thường kéo dài (lơ
đãng/ngủ gật/cúi nhìn xuống lâu).

BUG 1 ĐÃ SỬA (phát hiện khi test qua webcam thật — nhắm mắt hẳn vẫn không
"vượt ngưỡng"): công thức ban đầu tính khoảng cách Euclidean trực tiếp trên
toạ độ CHUẨN HOÁ thô (`landmarks.get`, x chia cho chiều rộng, y chia cho
chiều cao). Khi frame không vuông (VD 640x480), trộn dx/dy chuẩn hoá theo 2
tỉ lệ khác nhau làm méo EAR lên ~width/height (≈1.33 lần với 640x480) — EAR
đo được luôn CAO hơn giá trị thật, nên mắt nhắm thật vẫn không tụt xuống
dưới ngưỡng 0.21. Test tự động (unit test với landmark giả lập) không bắt
được lỗi này vì tự vô tình dựng dữ liệu test theo đúng kiểu "chuẩn hoá thô"
tương tự code — bug chỉ lộ ra khi test bằng khuôn mặt thật trên frame không
vuông. Đã sửa: dùng `landmarks.to_pixel(i, frame_shape)` (toạ độ PIXEL thật,
cùng đơn vị cho cả 2 trục) thay vì `landmarks.get(i)`.

BUG 2 ĐÃ SỬA (phát hiện Tuần 8, test qua webcam thật — quay đầu/liếc mắt
sang PHẢI hoặc XUỐNG bị nhầm thành "nhắm mắt", quay sang TRÁI thì không):
bản trước quyết định "đang nhắm mắt" dựa trên EAR TRUNG BÌNH của 2 mắt
(`(ear_left + ear_right) / 2`). Khi đầu/mắt quay lệch khỏi hướng chính diện
camera, landmark 2D của mắt bị "ép phối cảnh" (perspective foreshortening)
— mắt xa camera hơn (theo hướng quay) bị nén lại trong ảnh 2D, khiến EAR
TÍNH RA của riêng mắt đó tụt thấp dù mắt vẫn mở hoàn toàn, trong khi mắt kia
gần như không đổi. Lấy trung bình 2 mắt khiến 1 mắt bị nén đủ để kéo trung
bình xuống dưới ngưỡng, dù không mắt nào thực sự nhắm — false positive.
Nhắm mắt THẬT (chớp mắt, ngủ gật) luôn đối xứng: CẢ HAI mắt cùng nhắm. Đã
sửa: chỉ coi là "nhắm mắt" khi CẢ HAI EAR (không phải trung bình) đều dưới
ngưỡng — loại được phần lớn trường hợp méo 1 bên do quay đầu/liếc mắt, vẫn
giữ đúng hành vi với nhắm mắt thật (luôn đối xứng cả 2 mắt).

GIỚI HẠN CÒN LẠI (không thể giải quyết triệt để chỉ trong EyeStateSignal):
nếu đầu quay đủ NHIỀU, landmark của CẢ HAI mắt có thể cùng bị méo (không chỉ
1 bên), lúc đó cách sửa trên không còn tác dụng. Trường hợp này về bản chất
cần kết hợp với HEAD_POSE (nếu góc quay đầu đang lớn, giảm độ tin cậy của
EYE_STATE) — đây là lý do kinh điển cho tầng Risk Fusion Engine (Tuần 9) kết
hợp NHIỀU tín hiệu thay vì mỗi tín hiệu tự quyết định độc lập; đã ghi lại
làm input thiết kế cho Tuần 9 (xem docs/HUONG_DAN_DEMO_TUAN8.md /
ghi chú bug Tuần 8).
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from src.perception.perception_result import FaceLandmarks, PerceptionResult

from ._debounce import DurationDebounceTimer
from .base import SignalExtractor, SignalResult

# Xác minh qua mediapipe.tasks.python.vision.FaceLandmarksConnections trong venv:
# RIGHT_EYE chứa {7,33,133,144,145,153,154,155,157,158,159,160,161,163,173,246}
# LEFT_EYE  chứa {249,263,362,373,374,380,381,382,384,385,386,387,388,390,398,466}
# 6 điểm dưới đây là tập con chuẩn kiểu Soukupová & Čech (2 khoé + 2 trên + 2 dưới).
_RIGHT_EYE_P1_TO_P6: Tuple[int, int, int, int, int, int] = (33, 160, 158, 133, 153, 144)
_LEFT_EYE_P1_TO_P6: Tuple[int, int, int, int, int, int] = (362, 385, 387, 263, 373, 380)


def _euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _eye_aspect_ratio(landmarks: FaceLandmarks, points: Sequence[int], frame_shape: Tuple[int, int]) -> float:
    # QUAN TRỌNG: phải dùng toạ độ PIXEL (to_pixel), không phải toạ độ chuẩn
    # hoá thô (landmarks.get) — toạ độ chuẩn hoá của MediaPipe có x chia cho
    # chiều RỘNG và y chia cho chiều CAO khác nhau; khi frame không vuông
    # (VD 640x480), trộn dx/dy chuẩn hoá trong cùng 1 khoảng cách Euclidean
    # sẽ làm méo tỉ lệ EAR (lệch ~width/height, ví dụ 640/480 ≈ 1.33 lần) —
    # bug thật đã phát hiện khi test qua webcam thật: EAR đo được luôn cao
    # hơn giá trị đúng, khiến mắt nhắm thật cũng không tụt xuống dưới ngưỡng.
    p1, p2, p3, p4, p5, p6 = (landmarks.to_pixel(i, frame_shape) for i in points)
    vertical = _euclidean(p2, p6) + _euclidean(p3, p5)
    horizontal = _euclidean(p1, p4)
    if horizontal <= 1e-6:
        return 0.0
    return vertical / (2.0 * horizontal)


def calculate_eye_aspect_ratios(
    landmarks: FaceLandmarks, frame_shape: Tuple[int, int],
) -> Tuple[float, float]:
    """Return ``(left, right)`` EAR values for reuse by blink liveness."""
    ear_right = _eye_aspect_ratio(landmarks, _RIGHT_EYE_P1_TO_P6, frame_shape)
    ear_left = _eye_aspect_ratio(landmarks, _LEFT_EYE_P1_TO_P6, frame_shape)
    return ear_left, ear_right


class EyeStateSignal(SignalExtractor):
    signal_name = "EYE_STATE"

    def __init__(self, ear_threshold: float = 0.21, min_closed_duration_sec: float = 1.0) -> None:
        if ear_threshold <= 0:
            raise ValueError("ear_threshold phải > 0")
        self._ear_threshold = ear_threshold
        self._timer = DurationDebounceTimer(min_closed_duration_sec)

    def reset(self) -> None:
        self._timer.reset()

    def process(self, perception_result: PerceptionResult) -> SignalResult:
        now = perception_result.timestamp
        landmarks = perception_result.face_landmarks

        if landmarks is None:
            # Mất khuôn mặt -> không đủ dữ liệu đánh giá mắt; việc vắng mặt
            # đã do FacePresenceSignal xử lý riêng, ở đây chỉ reset timer.
            self._timer.reset()
            return SignalResult(
                signal_name=self.signal_name,
                timestamp=now,
                value=0.0,
                exceeds_threshold=False,
                confidence=0.0,
                metadata={"ear_left": None, "ear_right": None, "closed_duration_sec": 0.0},
            )

        ear_left, ear_right = calculate_eye_aspect_ratios(landmarks, perception_result.frame_shape)
        ear_avg = (ear_left + ear_right) / 2.0

        # CẢ HAI mắt phải dưới ngưỡng mới coi là nhắm (không dùng trung bình)
        # — tránh false positive khi quay đầu/liếc mắt làm méo phối cảnh 1
        # bên mắt (xem BUG 2 trong docstring module).
        both_eyes_closed = ear_left < self._ear_threshold and ear_right < self._ear_threshold
        closed_duration = self._timer.update(now, condition=both_eyes_closed)

        return SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=round(ear_avg, 4),
            exceeds_threshold=self._timer.exceeds(closed_duration),
            confidence=1.0,
            metadata={
                "ear_left": round(ear_left, 4),
                "ear_right": round(ear_right, 4),
                "closed_duration_sec": round(closed_duration, 2),
            },
        )
