"""MouthStateSignal — độ mở miệng dựa trên landmark môi MediaPipe FaceMesh.

    mouth_open_ratio = khoảng cách dọc môi trên/dưới (điểm trong)
                        / khoảng cách ngang khoé miệng trái-phải

Cùng nguyên lý chuẩn hoá theo tỉ lệ (bất biến với khoảng cách tới camera)
như EyeStateSignal (EAR), nhưng công thức tự thiết kế riêng cho miệng (không
phải EAR nguyên bản — cấu trúc hình học miệng khác mắt, không có 2 cặp điểm
trên/dưới đối xứng như mắt). 4 điểm landmark (13, 14, 61, 291) lấy từ tập
`FACE_LANDMARKS_LIPS` mà package `mediapipe` expose (đã xác minh trong venv).

LỊCH SỬ THIẾT KẾ: bản đầu tiên đếm THỜI GIAN MỞ LIÊN TỤC (giống
FacePresenceSignal/EyeStateSignal) — nhưng khi test qua webcam thật, nói
chuyện bình thường khiến miệng mở/ngậm xen kẽ liên tục theo từng từ/âm tiết,
nên gần như không bao giờ giữ mở liên tục đủ lâu để "vượt ngưỡng": chỉ bắt
được kiểu há miệng giữ nguyên (ngáp), bỏ sót chính hành vi cần phát hiện
(nói chuyện/thì thầm). Sửa lại: theo dõi TỈ LỆ THỜI GIAN MỞ trong 1 CỬA SỔ
TRƯỢT NGẮN (`activity_window_sec`) thay vì đếm chuỗi liên tục — bắt được cả
2 kiểu (mở liên tục 100% cửa sổ, LẪN mở/ngậm dồn dập khi nói chỉ chiếm một
phần cửa sổ nhưng đủ thường xuyên).

Đã đối chiếu với `mouth_detection.py` của dự án tham khảo (xem
docs/SO_SANH_KY_THUAT_TUAN4.md mục 2), phát hiện 3 điểm yếu cụ thể ở đó:
(1) 1 trong 2 landmark khoé miệng họ dùng (`306`) KHÔNG nằm trong tập
`FACE_LANDMARKS_LIPS` mà package thực sự expose (rất có thể gõ nhầm từ
`308`) — đúng kiểu lỗi mà việc verify landmark qua package cài đặt (thay vì
nhớ/chép số) được thiết kế để tránh; (2) độ mở đo bằng khoảng cách TUYỆT ĐỐI
(không chia cho kích thước mặt) nên phụ thuộc khoảng cách ngồi tới camera —
`ratio` ở đây tự chuẩn hoá nên tránh được; (3) ngưỡng tích luỹ của họ
(`movement_threshold`) tính bằng SỐ FRAME, không phải giây, nên hành vi đổi
theo FPS máy chạy — `activity_window_sec` ở đây tính bằng giây nên nhất
quán. Điểm họ làm đúng hướng (và được giữ lại ở đây bằng cơ chế chuẩn hơn):
dùng bộ đếm tích luỹ theo thời gian thay vì đòi hỏi 1 chuỗi liên tục không
ngắt — đây chính là bài học rút ra để sửa bug ở LỊCH SỬ THIẾT KẾ phía trên.

BUG THỨ 2 ĐÃ SỬA (cùng đợt phát hiện với bug tương tự ở EyeStateSignal khi
test qua webcam thật): công thức ban đầu tính `vertical`/`horizontal` trực
tiếp trên toạ độ CHUẨN HOÁ thô (`landmarks.get`) thay vì toạ độ PIXEL
(`landmarks.to_pixel`) — méo tỉ lệ theo width/height khi frame không vuông,
cùng bản chất lỗi đã ghi ở EyeStateSignal. Đã sửa dùng `to_pixel`.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Tuple

from src.perception.perception_result import PerceptionResult

from .base import SignalExtractor, SignalResult

_UPPER_LIP_INNER = 13
_LOWER_LIP_INNER = 14
_MOUTH_LEFT_CORNER = 61
_MOUTH_RIGHT_CORNER = 291


def _euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class MouthStateSignal(SignalExtractor):
    signal_name = "MOUTH_STATE"

    def __init__(
        self,
        open_ratio_threshold: float = 0.15,
        activity_window_sec: float = 2.0,
        activity_ratio_threshold: float = 0.25,
        min_window_coverage_sec: float = 1.0,
    ) -> None:
        if open_ratio_threshold <= 0:
            raise ValueError("open_ratio_threshold phải > 0")
        if activity_window_sec <= 0:
            raise ValueError("activity_window_sec phải > 0")
        if not 0.0 < activity_ratio_threshold <= 1.0:
            raise ValueError("activity_ratio_threshold phải trong (0, 1]")
        if min_window_coverage_sec <= 0 or min_window_coverage_sec > activity_window_sec:
            raise ValueError("min_window_coverage_sec phải > 0 và <= activity_window_sec")

        self._open_ratio_threshold = open_ratio_threshold
        self._activity_window_sec = activity_window_sec
        self._activity_ratio_threshold = activity_ratio_threshold
        self._min_window_coverage_sec = min_window_coverage_sec
        # (timestamp, is_open) của các frame gần đây, giới hạn trong activity_window_sec.
        self._history: Deque[Tuple[float, bool]] = deque()

    def reset(self) -> None:
        self._history.clear()

    def _push_and_trim(self, now: float, is_open: bool) -> None:
        self._history.append((now, is_open))
        while self._history and (now - self._history[0][0]) > self._activity_window_sec:
            self._history.popleft()

    def _activity_ratio(self, now: float) -> float:
        if not self._history:
            return 0.0
        # Chưa đủ dữ liệu bao phủ tối thiểu (VD mới bắt đầu phiên) -> chưa kết luận.
        window_span = now - self._history[0][0]
        if window_span < self._min_window_coverage_sec:
            return 0.0
        open_count = sum(1 for _, is_open in self._history if is_open)
        return open_count / len(self._history)

    def process(self, perception_result: PerceptionResult) -> SignalResult:
        now = perception_result.timestamp
        landmarks = perception_result.face_landmarks

        if landmarks is None:
            self._history.clear()
            return SignalResult(
                signal_name=self.signal_name,
                timestamp=now,
                value=0.0,
                exceeds_threshold=False,
                confidence=0.0,
                metadata={"mouth_open_ratio": None, "activity_ratio": 0.0},
            )

        # Dùng toạ độ PIXEL (to_pixel), không phải chuẩn hoá thô (landmarks.get)
        # — cùng lý do đã sửa ở EyeStateSignal: trộn dx/dy chuẩn hoá trên frame
        # không vuông sẽ làm méo tỉ lệ mở miệng theo width/height thật.
        frame_shape = perception_result.frame_shape
        vertical = _euclidean(
            landmarks.to_pixel(_UPPER_LIP_INNER, frame_shape),
            landmarks.to_pixel(_LOWER_LIP_INNER, frame_shape),
        )
        horizontal = _euclidean(
            landmarks.to_pixel(_MOUTH_LEFT_CORNER, frame_shape),
            landmarks.to_pixel(_MOUTH_RIGHT_CORNER, frame_shape),
        )
        ratio = vertical / horizontal if horizontal > 1e-6 else 0.0
        is_open = ratio >= self._open_ratio_threshold

        self._push_and_trim(now, is_open)
        activity_ratio = self._activity_ratio(now)

        return SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=round(ratio, 4),
            exceeds_threshold=activity_ratio >= self._activity_ratio_threshold,
            confidence=1.0,
            metadata={
                "mouth_open_ratio": round(ratio, 4),
                "activity_ratio": round(activity_ratio, 4),
                "window_samples": len(self._history),
            },
        )
