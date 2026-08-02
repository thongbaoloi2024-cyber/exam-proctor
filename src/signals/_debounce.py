"""DurationDebounceTimer — theo dõi 1 điều kiện boolean có ĐANG ĐÚNG LIÊN TỤC
bao lâu, chỉ coi là "vượt ngưỡng" khi đủ lâu.

Rút ra thành helper dùng chung khi rà soát Tuần 7 phát hiện 4/7 signal
(FacePresenceSignal, EyeStateSignal, ObjectSignal, HeadPoseSignal) cài đặt
gần như y hệt cùng 1 đoạn logic (bộ đếm `_started_at`, reset khi điều kiện
sai). 3 signal còn lại KHÔNG dùng pattern này vì bản chất hiện tượng khác:
- MouthStateSignal: dao động nhanh (nói chuyện = mở/ngậm liên tục) -> cần tỉ
  lệ % thời gian trong 1 cửa sổ trượt, không phải chuỗi liên tục không ngắt
  (xem lịch sử bug trong src/signals/mouth_state.py).
- IdentitySignal: chu kỳ kiểm tra thưa (mỗi 30s, không phải mỗi frame) -> cần
  đếm SỐ LẦN fail liên tiếp qua các chu kỳ throttle, không phải số giây.
- MultiFaceSignal: không cần debounce thời gian (đếm số khuôn mặt tức thời).
"""

from __future__ import annotations

from typing import Optional


class DurationDebounceTimer:
    def __init__(self, min_duration_sec: float) -> None:
        if min_duration_sec <= 0:
            raise ValueError("min_duration_sec phải > 0")
        self.min_duration_sec = min_duration_sec
        self._started_at: Optional[float] = None

    def reset(self) -> None:
        self._started_at = None

    def update(self, now: float, condition: bool) -> float:
        """Cập nhật trạng thái tại thời điểm `now` với `condition` hiện tại.

        Trả về số giây đã ĐÚNG LIÊN TỤC (0.0 nếu `condition` là False, hoặc
        nếu đây là frame đầu tiên condition vừa chuyển thành True)."""
        if not condition:
            self._started_at = None
            return 0.0
        if self._started_at is None:
            self._started_at = now
        return now - self._started_at

    def exceeds(self, duration_sec: float) -> bool:
        return duration_sec >= self.min_duration_sec
