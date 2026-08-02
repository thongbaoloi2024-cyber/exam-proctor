"""Benchmark hiệu năng Tuần 7: đo FPS/bottleneck của pipeline (PerceptionLayer
+ 7 signal) trên MÁY ĐANG CHẠY script này — không cần webcam, dùng frame
synthetic (nền đen) lặp lại nhiều lần để đo chi phí TÍNH TOÁN thuần tuý (CPU
model inference + logic signal), tách biệt khỏi chi phí đọc webcam/hiển thị
màn hình (không phải phần cần tối ưu của pipeline CV).

Chạy: python scripts/benchmark_fps.py [--frames N]

Lưu ý quan trọng khi đọc kết quả:
- Frame nền đen -> không phát hiện khuôn mặt/vật thể thật, nhưng chi phí
  model (MTCNN/FaceMesh/YOLO) gần như KHÔNG đổi dù có mặt hay không (vẫn phải
  chạy forward pass đầy đủ) -> số đo phần Perception Layer vẫn phản ánh đúng
  chi phí thực tế.
- IdentitySignal KHÔNG được enroll trong benchmark chính (không có khuôn mặt
  thật để enroll) -> luôn đi theo nhánh rẻ "chưa enroll", không đại diện cho
  chi phí thật của việc re-verify (chạy model embedding riêng mỗi 30s). Chi
  phí đó được đo RIÊNG (mục 2 bên dưới) và không cộng vào FPS chính vì tần
  suất quá thấp (1 lần/30s) so với 1 frame/33ms.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# scripts/ khong tu dong co repo root tren sys.path khi chay truc tiep
# (python scripts/benchmark_fps.py) - them vao de import duoc package src.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from src.orchestrator import PipelineOrchestrator
from src.perception.face_embedder import FaceEmbedder
from src.perception.pipeline import PerceptionLayer
from src.signals.eye_state import EyeStateSignal
from src.signals.face_presence import FacePresenceSignal
from src.signals.head_pose import HeadPoseSignal
from src.signals.identity import IdentitySignal
from src.signals.mouth_state import MouthStateSignal
from src.signals.multi_face import MultiFaceSignal
from src.signals.object_signal import ObjectSignal

WARMUP_FRAMES = 5


def _build_signals():
    return [
        FacePresenceSignal(),
        MultiFaceSignal(),
        EyeStateSignal(),
        MouthStateSignal(),
        ObjectSignal(),
        HeadPoseSignal(),
        IdentitySignal(),
    ]


def benchmark_main_pipeline(num_frames: int) -> dict:
    print(f"Dang khoi tao PerceptionLayer + 7 signal (tai model lan dau co the mat vai chuc giay)...")
    perception = PerceptionLayer()
    orchestrator = PipelineOrchestrator(perception, _build_signals())

    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    print(f"Warmup {WARMUP_FRAMES} frame...")
    for _ in range(WARMUP_FRAMES):
        orchestrator.process_frame(blank_frame)

    print(f"Do hieu nang tren {num_frames} frame...")
    t0 = time.perf_counter()
    for _ in range(num_frames):
        orchestrator.process_frame(blank_frame)
    total_wall_sec = time.perf_counter() - t0

    report = orchestrator.performance_report()
    orchestrator.close()

    overall_fps = num_frames / total_wall_sec if total_wall_sec > 0 else 0.0
    return {"report": report, "overall_fps": overall_fps, "num_frames": num_frames}


def benchmark_identity_embedding(num_calls: int = 5) -> float:
    print("Do rieng chi phi FaceEmbedder.extract() (MTCNN align + InceptionResnetV1)...")
    embedder = FaceEmbedder()
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    embedder.extract(blank_frame)  # warmup

    t0 = time.perf_counter()
    for _ in range(num_calls):
        embedder.extract(blank_frame)
    elapsed = time.perf_counter() - t0
    return (elapsed / num_calls) * 1000.0  # ms/call


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark FPS pipeline giam sat thi")
    parser.add_argument("--frames", type=int, default=60, help="So frame dung de do (mac dinh 60)")
    args = parser.parse_args()

    result = benchmark_main_pipeline(args.frames)
    report = result["report"]

    print("\n=== KET QUA BENCHMARK ===")
    print(f"So frame do: {result['num_frames']}")
    print(f"FPS tong the (loop lien tuc, khong tinh webcam/hien thi): {result['overall_fps']:.1f}")
    print("\nChi phi trung binh tung buoc (ms/frame), sap xep giam dan:")
    for name, ms in sorted(report.items(), key=lambda kv: -kv[1]):
        bar = "#" * max(1, int(ms))
        print(f"  {name:<20s} {ms:7.2f} ms  {bar}")
    total_ms = sum(report.values())
    print(f"\nTong chi phi tinh toan: {total_ms:.2f} ms/frame (tuong duong {1000.0/total_ms:.1f} FPS ly thuyet)")

    identity_ms = benchmark_identity_embedding()
    print(f"\nChi phi FaceEmbedder.extract() (chi chay 1 lan moi reverify_interval_sec, KHONG nam trong FPS chinh): {identity_ms:.1f} ms/lan")
    print("-> Neu chay dong bo (block) trong vong lap chinh, se gay giat 1 frame moi 30s bang dung luong nay.")


if __name__ == "__main__":
    main()
