"""Interface chung cho mọi Signal Extractor — theo docs/DATA_SCHEMAS.md mục 2.

Mỗi signal extractor nhận `PerceptionResult` (đã dùng chung 1 lần chạy detector
cho cả frame, xem `src/perception/pipeline.py`) và trả về đúng 1 `SignalResult`.

`SignalResult` KHÔNG có field `state` — trạng thái NORMAL/SUSPICIOUS/ALERT do
Risk Fusion Engine gán sau (Tuần 9), không phải trách nhiệm của signal
extractor, để 2 tầng tách biệt rõ ràng.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict

from src.perception.perception_result import PerceptionResult


@dataclass
class SignalResult:
    signal_name: str
    timestamp: float
    value: float
    exceeds_threshold: bool
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class SignalExtractor(ABC):
    """Base class cho mọi signal extractor.

    Có state nội bộ (VD bộ đếm thời gian vắng mặt liên tục của
    `FacePresenceSignal`) nên mỗi phiên giám sát cần khởi tạo instance mới,
    hoặc gọi `reset()` khi bắt đầu phiên mới.
    """

    signal_name: ClassVar[str]

    @abstractmethod
    def process(self, perception_result: PerceptionResult) -> SignalResult:
        """Xử lý kết quả perception của 1 frame, trả về SignalResult tương ứng."""
        raise NotImplementedError

    def reset(self) -> None:
        """Xoá state nội bộ (bộ đếm thời gian, v.v.). Mặc định không làm gì."""
        return None
