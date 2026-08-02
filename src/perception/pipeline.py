"""PerceptionLayer: gộp preprocessor + các detector thành 1 bước xử lý/frame.

Nhận 1 frame BGR thô (từ FrameSource hoặc từ file test), trả về
(PreprocessedFrame, PerceptionResult) — đúng luồng mô tả ở sequence diagram
`docs/DIAGRAMS.md` mục 2 (ORCH->PERC: preprocess_and_detect(raw_frame)).

MTCNN và FaceMesh chạy MỖI frame (đủ nhẹ cho real-time). YOLO (object
detection) được THROTTLE theo thời gian (`object_detect_interval_sec`) vì
tốn tài nguyên hơn hẳn — giữa 2 lần detect, dùng lại kết quả gần nhất
(`_last_objects`) thay vì để trống, để ObjectSignal vẫn tính được thời gian
xuất hiện liên tục một cách hợp lý.

Mỗi lần gọi detector được bọc an toàn (`_safe_call`): nếu 1 detector lỗi ở 1
frame (ảnh hỏng, hết bộ nhớ tạm thời...), pipeline dùng kết quả dự phòng
(rỗng, hoặc kết quả gần nhất với YOLO) thay vì crash cả phiên giám sát đang
chạy giữa buổi thi — quyết định thêm sau khi đối chiếu với bản tham khảo
(vốn có try/except quanh mọi detector), xem docs/SO_SANH_KY_THUAT_TUAN4.md
mục 3.

`last_timings` (giây) ghi lại thời gian mỗi bước tốn ở lần `process()` GẦN
NHẤT — phục vụ đo hiệu năng/tìm bottleneck (Tuần 7,
`scripts/benchmark_fps.py`). `object_detect` = 0.0 ở những frame bị throttle
(không thực sự chạy YOLO) — cố ý, để khi lấy trung bình nhiều frame ra đúng
"chi phí đã khấu hao" (amortized cost) của YOLO trên mỗi frame, không phải
chi phí của riêng những frame nó thực sự chạy.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple, TypeVar

import numpy as np

from .frame_source import now
from .perception_result import FaceBox, FaceLandmarks, ObjectBox, PerceptionResult
from .preprocessor import FramePreprocessor, PreprocessedFrame

if TYPE_CHECKING:
    from .face_detector import MTCNNFaceDetector
    from .face_mesh_detector import FaceMeshDetector
    from .object_detector import YOLOObjectDetector

T = TypeVar("T")


class PerceptionLayer:
    def __init__(
        self,
        preprocessor: Optional[FramePreprocessor] = None,
        face_detector: Optional[MTCNNFaceDetector] = None,
        face_mesh_detector: Optional[FaceMeshDetector] = None,
        object_detector: Optional[YOLOObjectDetector] = None,
        object_detect_interval_sec: float = 0.4,
    ) -> None:
        if object_detect_interval_sec <= 0:
            raise ValueError("object_detect_interval_sec phải > 0")

        self._preprocessor = preprocessor or FramePreprocessor()

        # Model backends are optional when callers inject detector fakes.  Load
        # each concrete class only when its default instance is really needed.
        if face_detector is None:
            from .face_detector import MTCNNFaceDetector

            face_detector = MTCNNFaceDetector()
        if face_mesh_detector is None:
            from .face_mesh_detector import FaceMeshDetector

            face_mesh_detector = FaceMeshDetector()
        if object_detector is None:
            from .object_detector import YOLOObjectDetector

            object_detector = YOLOObjectDetector()

        self._face_detector = face_detector
        self._face_mesh_detector = face_mesh_detector
        self._object_detector = object_detector
        self._object_detect_interval_sec = object_detect_interval_sec

        self._last_object_detect_at: Optional[float] = None
        self._last_objects: List[ObjectBox] = []
        self.last_timings: Dict[str, float] = {}

    @staticmethod
    def _safe_call(fn: Callable[[], T], fallback: T, context: str) -> T:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - cố ý bắt mọi lỗi để không sập pipeline
            print(f"[PerceptionLayer] {context} loi, dung ket qua du phong: {exc}", file=sys.stderr)
            return fallback

    @staticmethod
    def _timed(fn: Callable[[], T]) -> Tuple[T, float]:
        t0 = time.perf_counter()
        value = fn()
        return value, time.perf_counter() - t0

    def process(self, raw_frame_bgr: np.ndarray) -> Tuple[PreprocessedFrame, PerceptionResult]:
        preprocessed, t_preprocess = self._timed(lambda: self._preprocessor.process(raw_frame_bgr))
        ts = now()

        face_boxes: List[FaceBox]
        face_boxes, t_face_detect = self._timed(
            lambda: self._safe_call(
                lambda: self._face_detector.detect(preprocessed.rgb),
                fallback=[],
                context="MTCNNFaceDetector.detect",
            )
        )
        face_landmarks: Optional[FaceLandmarks]
        face_landmarks, t_face_mesh = self._timed(
            lambda: self._safe_call(
                lambda: self._face_mesh_detector.detect(preprocessed.rgb),
                fallback=None,
                context="FaceMeshDetector.detect",
            )
        )

        should_run_object_detect = (
            self._last_object_detect_at is None
            or (ts - self._last_object_detect_at) >= self._object_detect_interval_sec
        )
        t_object_detect = 0.0
        if should_run_object_detect:
            self._last_objects, t_object_detect = self._timed(
                lambda: self._safe_call(
                    lambda: self._object_detector.detect(preprocessed.resized_bgr),
                    fallback=self._last_objects,
                    context="YOLOObjectDetector.detect",
                )
            )
            self._last_object_detect_at = ts

        self.last_timings = {
            "preprocess": t_preprocess,
            "face_detect": t_face_detect,
            "face_mesh": t_face_mesh,
            "object_detect": t_object_detect,
        }

        result = PerceptionResult(
            timestamp=ts,
            frame_shape=preprocessed.rgb.shape[:2],
            face_boxes=face_boxes,
            face_landmarks=face_landmarks,
            objects=self._last_objects,
            rgb_frame=preprocessed.rgb,
        )
        return preprocessed, result
