"""Download and initialize every CV model required by the desktop client.

Run this once while online before an offline exam/demo.  Downloaded weights
are kept under ``models/`` (gitignored) and are deliberately not bundled with
the source archive because of their size and upstream licenses.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.perception.face_detector import MTCNNFaceDetector
from src.perception.face_embedder import FaceEmbedder
from src.perception.face_mesh_detector import FaceMeshDetector
from src.perception.object_detector import YOLOObjectDetector


def main() -> None:
    print("Initializing MTCNN...")
    MTCNNFaceDetector()
    print("Downloading/initializing FaceNet VGGFace2...")
    FaceEmbedder()
    print("Downloading/initializing MediaPipe FaceLandmarker...")
    FaceMeshDetector()
    print("Downloading/initializing YOLOv8n...")
    YOLOObjectDetector()
    print(f"All model assets are ready under: {PROJECT_ROOT / 'models'}")


if __name__ == "__main__":
    main()
