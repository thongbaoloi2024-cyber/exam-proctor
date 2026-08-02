"""HeadPoseSignal — phát hiện "nhìn ra ngoài màn hình" bằng góc quay đầu
thật (yaw/pitch, độ) từ cv2.solvePnP, thay cho cách so lệch pixel mắt-mũi
thô của bản tham khảo (không có chiều sâu, dễ sai khi đầu nghiêng — xem
docs/DE_CUONG_CHI_TIET.md mục 5.1 và docs/SO_SANH_KY_THUAT_TUAN4.md).

Toán học lõi (đọc landmark, mô hình 3D chuẩn, camera matrix xấp xỉ, giải PnP
+ decode Euler) nằm ở `src/perception/head_pose_math.py`, đã kiểm chứng bằng
test tổng hợp (dựng góc quay biết trước, chiếu ngược ra landmark, giải lại
xem có khớp không — tests/test_head_pose_math.py). Xem
docs/HEAD_POSE_NOTES.md cho giải thích đầy đủ + giới hạn phương pháp.

Debounce theo thời gian NHÌN LỆCH LIÊN TỤC (`min_away_duration_sec`) — cùng
triết lý FacePresenceSignal/EyeStateSignal: quay đầu thoáng qua (liếc nhanh)
không tính là vi phạm, chỉ khi góc vượt ngưỡng ĐỦ LÂU mới cảnh báo.
"""

from __future__ import annotations

from typing import Optional

from src.perception.head_pose_math import HeadPoseResult, solve_head_pose
from src.perception.perception_result import PerceptionResult

from ._debounce import DurationDebounceTimer
from .base import SignalExtractor, SignalResult


class HeadPoseSignal(SignalExtractor):
    signal_name = "HEAD_POSE"

    def __init__(
        self,
        yaw_threshold_deg: float = 20.0,
        pitch_threshold_deg: float = 20.0,
        min_away_duration_sec: float = 1.0,
    ) -> None:
        if yaw_threshold_deg <= 0 or pitch_threshold_deg <= 0:
            raise ValueError("yaw_threshold_deg/pitch_threshold_deg phải > 0")

        self._yaw_threshold_deg = yaw_threshold_deg
        self._pitch_threshold_deg = pitch_threshold_deg
        self._timer = DurationDebounceTimer(min_away_duration_sec)

    def reset(self) -> None:
        self._timer.reset()

    def _no_data_result(self, now: float) -> SignalResult:
        return SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=0.0,
            exceeds_threshold=False,
            confidence=0.0,
            metadata={"yaw": None, "pitch": None, "roll": None, "away_duration_sec": 0.0},
        )

    def process(self, perception_result: PerceptionResult) -> SignalResult:
        now = perception_result.timestamp
        landmarks = perception_result.face_landmarks

        if landmarks is None:
            self._timer.reset()
            return self._no_data_result(now)

        result: Optional[HeadPoseResult] = solve_head_pose(landmarks, perception_result.frame_shape)
        if result is None:
            # solvePnP hiếm khi không hội tụ (6 điểm gần suy biến) -> coi như
            # không đủ dữ liệu đáng tin cậy, không kết luận vội, giữ nguyên
            # timer để 1 frame lỗi thoáng qua không reset chuỗi đang đếm.
            return self._no_data_result(now)

        is_away = abs(result.yaw_deg) >= self._yaw_threshold_deg or abs(result.pitch_deg) >= self._pitch_threshold_deg
        away_duration = self._timer.update(now, condition=is_away)

        return SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=round(result.yaw_deg, 2),
            exceeds_threshold=self._timer.exceeds(away_duration),
            confidence=1.0,
            metadata={
                "yaw": round(result.yaw_deg, 2),
                "pitch": round(result.pitch_deg, 2),
                "roll": round(result.roll_deg, 2),
                "away_duration_sec": round(away_duration, 2),
                # Giữ lại để vẽ trực quan debug (main.py) mà không phải giải PnP lại lần 2.
                "rotation_vector": result.rotation_vector.tolist(),
                "translation_vector": result.translation_vector.tolist(),
                "camera_matrix": result.camera_matrix.tolist(),
                "nose_2d_px": list(result.nose_2d_px),
            },
        )
