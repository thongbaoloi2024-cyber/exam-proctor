"""IdentitySignal — xác thực danh tính xuyên suốt phiên thi bằng face
embedding (facenet-pytorch, InceptionResnetV1 pretrained vggface2).

Kỹ thuật mới thứ 2 của đồ án — bản tham khảo HOÀN TOÀN không có khả năng
này (chỉ đếm số khuôn mặt bằng MultiFaceSignal-kiểu-tương-đương, không xác
minh khuôn mặt đó có đúng là thí sinh đã đăng ký hay không). Xem
docs/DE_CUONG_CHI_TIET.md mục 5.2 và docs/IDENTITY_NOTES.md cho cách chọn
ngưỡng cosine similarity + giới hạn phương pháp (dùng cho luận văn).

2 GIAI ĐOẠN TÁCH BIỆT:

1. ENROLLMENT (gọi 1 LẦN lúc bắt đầu phiên qua `enroll(rgb_frames)`, KHÔNG
   phải qua `process()`): thu thập embedding từ vài frame đầu (thường 3-5),
   lấy TRUNG BÌNH làm embedding tham chiếu — trung bình giúp ổn định hơn 1
   frame đơn lẻ (nhiễu ánh sáng/góc mặt thoáng qua lúc bắt đầu). Nếu KHÔNG
   frame nào tìm thấy khuôn mặt -> `enroll()` trả False, người gọi (VD
   main.py) cần thử lại (yêu cầu thí sinh nhìn thẳng camera) — xử lý edge
   case theo đúng yêu cầu Tuần 6.

2. RE-VERIFICATION định kỳ (trong `process()`, gọi MỖI FRAME nhưng chỉ thực
   sự chạy embedding model mỗi `reverify_interval_sec` giây — throttle NỘI
   BỘ trong signal này, cùng triết lý throttle YOLO ở PerceptionLayer Tuần
   4, nhưng đặt trong signal vì embedding model không dùng chung với signal
   nào khác nên không cần đưa lên Perception Layer): so cosine similarity
   giữa embedding hiện tại và embedding tham chiếu.

NGƯỠNG CÓ BIÊN ĐỘ (2 mức, không phải 1 ngưỡng nhị phân đơn giản) — theo
đúng yêu cầu edge case "ánh sáng thay đổi, tránh false positive quá nhạy":
- similarity >= cosine_threshold_warn  -> khớp bình thường
- cosine_threshold_alert <= similarity < cosine_threshold_warn -> "cảnh báo
  nhẹ" (`metadata["warning"]=True`), CHƯA kết luận đổi người — độ giống có
  giảm (có thể do ánh sáng/góc mặt) nhưng chưa đủ thấp để chắc chắn
- similarity < cosine_threshold_alert -> tính là 1 LẦN "fail"

KHÔNG kết luận IDENTITY_MISMATCH (`exceeds_threshold=True`) ngay từ 1 lần
fail — cần `consecutive_failures_required` lần fail LIÊN TIẾP (mặc định 2,
tức 2 chu kỳ re-verify ~60s dữ liệu thấp liên tục) mới chắc chắn kết luận,
tránh 1 lần đọc lỗi thoáng qua (mờ, chuyển động, ánh sáng chớp) gây báo động
giả — đây là phần "biên độ" tự thiết kế theo đúng gợi ý rủi ro ở
KE_HOACH_DO_AN.md mục 5.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from src.perception.face_embedder import FaceEmbedder, cosine_similarity
from src.perception.perception_result import PerceptionResult

from .base import SignalExtractor, SignalResult


class IdentitySignal(SignalExtractor):
    signal_name = "IDENTITY"

    def __init__(
        self,
        embedder: Optional[FaceEmbedder] = None,
        reverify_interval_sec: float = 30.0,
        cosine_threshold_warn: float = 0.60,
        cosine_threshold_alert: float = 0.45,
        consecutive_failures_required: int = 2,
    ) -> None:
        if reverify_interval_sec <= 0:
            raise ValueError("reverify_interval_sec phải > 0")
        if not -1.0 <= cosine_threshold_alert < cosine_threshold_warn <= 1.0:
            raise ValueError("cần cosine_threshold_alert < cosine_threshold_warn, cả 2 trong [-1, 1]")
        if consecutive_failures_required < 1:
            raise ValueError("consecutive_failures_required phải >= 1")

        # Initialize the multi-hundred-megabyte model only when enrollment is
        # actually attempted.  Merely constructing the signal (for config
        # validation, backend imports, or a non-enrolled session) stays light.
        self._embedder = embedder
        self._reverify_interval_sec = reverify_interval_sec
        self._cosine_threshold_warn = cosine_threshold_warn
        self._cosine_threshold_alert = cosine_threshold_alert
        self._consecutive_failures_required = consecutive_failures_required

        self._reference_embedding: Optional[np.ndarray] = None
        self._last_verified_at: Optional[float] = None
        self._consecutive_failures = 0
        self._last_result: Optional[SignalResult] = None

    @property
    def is_enrolled(self) -> bool:
        return self._reference_embedding is not None

    def _get_embedder(self) -> FaceEmbedder:
        if self._embedder is None:
            self._embedder = FaceEmbedder()
        return self._embedder

    def enroll(self, rgb_frames: List[np.ndarray]) -> bool:
        """Thu thập embedding tham chiếu từ danh sách frame lúc bắt đầu
        phiên. Trả False nếu KHÔNG frame nào tìm thấy khuôn mặt (gọi lại)."""
        embedder = self._get_embedder()
        embeddings = [e for e in (embedder.extract(f) for f in rgb_frames) if e is not None]
        if not embeddings:
            return False

        self._reference_embedding = np.mean(embeddings, axis=0)
        self._last_verified_at = None
        self._consecutive_failures = 0
        self._last_result = None
        return True

    def reset(self) -> None:
        self._reference_embedding = None
        self._last_verified_at = None
        self._consecutive_failures = 0
        self._last_result = None

    def _not_enrolled_result(self, now: float) -> SignalResult:
        return SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=0.0,
            exceeds_threshold=False,
            confidence=0.0,
            metadata={"enrolled": False, "similarity": None, "warning": False},
        )

    def process(self, perception_result: PerceptionResult) -> SignalResult:
        now = perception_result.timestamp

        if self._reference_embedding is None:
            return self._not_enrolled_result(now)

        should_reverify = (
            self._last_verified_at is None or (now - self._last_verified_at) >= self._reverify_interval_sec
        )
        if not should_reverify:
            # Chưa tới chu kỳ re-verify -> giữ nguyên kết quả lần gần nhất
            # (không tính lại embedding mỗi frame - quá tốn tài nguyên).
            return self._last_result if self._last_result is not None else self._not_enrolled_result(now)

        rgb_frame = perception_result.rgb_frame
        if rgb_frame is None:
            return self._last_result if self._last_result is not None else self._not_enrolled_result(now)

        embedding = self._get_embedder().extract(rgb_frame)
        self._last_verified_at = now

        if embedding is None:
            # Không tìm thấy khuôn mặt lúc verify -> không đủ dữ liệu để kết
            # luận (KHÁC với "similarity thấp") - không tính là fail, việc
            # vắng mặt khuôn mặt đã do FacePresenceSignal xử lý riêng. Giữ
            # nguyên kết quả gần nhất, chờ chu kỳ verify tiếp theo.
            return self._last_result if self._last_result is not None else self._not_enrolled_result(now)

        similarity = cosine_similarity(embedding, self._reference_embedding)

        if similarity < self._cosine_threshold_alert:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

        is_mismatch = self._consecutive_failures >= self._consecutive_failures_required
        is_warning = self._cosine_threshold_alert <= similarity < self._cosine_threshold_warn

        result = SignalResult(
            signal_name=self.signal_name,
            timestamp=now,
            value=round(similarity, 4),
            exceeds_threshold=is_mismatch,
            confidence=1.0,
            metadata={
                "enrolled": True,
                "similarity": round(similarity, 4),
                "warning": is_warning,
                "consecutive_failures": self._consecutive_failures,
            },
        )
        self._last_result = result
        return result
