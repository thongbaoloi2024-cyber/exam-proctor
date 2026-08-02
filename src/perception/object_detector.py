"""Bọc YOLOv8 (ultralytics, pretrained COCO) — chỉ giữ lại 2 lớp liên quan
tới đồ án: "cell phone" (id 67) và "book" (id 73) trong bộ 80 lớp COCO chuẩn
mà ultralytics dùng (đã xác minh trực tiếp qua `model.names`, không đoán id).

Việc chạy YOLO tốn tài nguyên hơn hẳn MTCNN/FaceMesh — throttle tần suất gọi
KHÔNG nằm ở class này mà ở `PerceptionLayer` (`object_detect_interval_sec`),
để `YOLOObjectDetector` chỉ có 1 trách nhiệm duy nhất: detect đúng 1 frame
khi được gọi.

`confidence_threshold` mặc định (0.55) chọn sau khi đối chiếu với bản tham
khảo (xem docs/SO_SANH_KY_THUAT_TUAN4.md mục 3): bản tham khảo dùng
`min_confidence=0.65` (ưu tiên tránh báo động giả — nghi oan thí sinh có hậu
quả nặng hơn bỏ sót 1 lần). 0.55 là điểm giữa 0.40 (lựa chọn ban đầu, chưa
có cơ sở) và 0.65 (của bản tham khảo, chưa chắc đúng cho pipeline riêng của
đồ án) — sẽ tinh chỉnh bằng thực nghiệm thật ở Tuần 14.

`imgsz` mặc định 640 (KHÔNG downscale thêm so với frame đã resize sẵn ở
Perception Layer). Từng thử hạ xuống 320 theo bản tham khảo (giảm tải CPU)
nhưng test qua webcam thật cho thấy YOLOv8n bỏ sót vật thể ở góc nhìn khó
(VD mặt lưng điện thoại — ít đặc trưng phân biệt hơn mặt trước có màn
hình/camera, và bộ COCO gốc cũng thiên lệch nhiều ảnh chụp mặt trước điện
thoại hơn) — hạ độ phân giải trước khi đưa vào model càng làm mất thêm chi
tiết vốn đã ít. Trả về 640 để không tự làm giảm recall thêm; nếu vẫn còn bỏ
sót (nhiều khả năng do hạn chế bản thân model pretrained, không phải do
imgsz), phương án tiếp theo là thử model lớn hơn (`yolov8s.pt`) — đánh đổi
tốc độ lấy độ chính xác, cần đo bằng thực nghiệm Tuần 14 chứ không đoán.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np

from .perception_result import ObjectBox

TARGET_CLASS_NAMES = {"cell phone", "book"}
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODEL_PATH = _PROJECT_ROOT / "models" / "yolov8n.pt"


class YOLOObjectDetector:
    def __init__(
        self,
        model_name: str = str(_DEFAULT_MODEL_PATH),
        confidence_threshold: float = 0.55,
        imgsz: int = 640,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold phải trong [0, 1]")
        if imgsz <= 0:
            raise ValueError("imgsz phải > 0")

        self._confidence_threshold = confidence_threshold
        self._imgsz = imgsz
        # Importing Ultralytics also imports PyTorch.  Keep that cost local to
        # the concrete detector and store downloaded weights in the ignored
        # project model cache instead of whichever directory launched Python.
        from ultralytics import YOLO

        Path(model_name).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._model = YOLO(model_name)

        names: Dict[int, str] = self._model.names
        self._target_class_ids = [cid for cid, name in names.items() if name in TARGET_CLASS_NAMES]
        if not self._target_class_ids:
            raise RuntimeError(
                f"Model {model_name!r} không có lớp nào trong {TARGET_CLASS_NAMES} "
                "-- kiểm tra lại đây có đúng model COCO 80 lớp không."
            )

    def detect(self, bgr_frame: np.ndarray) -> List[ObjectBox]:
        results = self._model.predict(
            bgr_frame,
            classes=self._target_class_ids,
            conf=self._confidence_threshold,
            imgsz=self._imgsz,
            verbose=False,
        )

        boxes: List[ObjectBox] = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = self._model.names[class_id]
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                boxes.append(ObjectBox(bbox=(x1, y1, x2, y2), confidence=confidence, class_name=class_name))
        return boxes
