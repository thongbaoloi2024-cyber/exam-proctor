"""Perception package with lazy exports to avoid loading models on import."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "FrameSource": ("src.perception.frame_source", "FrameSource"),
    "FramePreprocessor": ("src.perception.preprocessor", "FramePreprocessor"),
    "PreprocessedFrame": ("src.perception.preprocessor", "PreprocessedFrame"),
    "FaceBox": ("src.perception.perception_result", "FaceBox"),
    "FaceLandmarks": ("src.perception.perception_result", "FaceLandmarks"),
    "ObjectBox": ("src.perception.perception_result", "ObjectBox"),
    "PerceptionResult": ("src.perception.perception_result", "PerceptionResult"),
    "MTCNNFaceDetector": ("src.perception.face_detector", "MTCNNFaceDetector"),
    "FaceMeshDetector": ("src.perception.face_mesh_detector", "FaceMeshDetector"),
    "YOLOObjectDetector": ("src.perception.object_detector", "YOLOObjectDetector"),
    "PerceptionLayer": ("src.perception.pipeline", "PerceptionLayer"),
    "HeadPoseResult": ("src.perception.head_pose_math", "HeadPoseResult"),
    "estimate_camera_matrix": ("src.perception.head_pose_math", "estimate_camera_matrix"),
    "solve_head_pose": ("src.perception.head_pose_math", "solve_head_pose"),
    "project_debug_axes": ("src.perception.head_pose_math", "project_debug_axes"),
    "FaceEmbedder": ("src.perception.face_embedder", "FaceEmbedder"),
    "cosine_similarity": ("src.perception.face_embedder", "cosine_similarity"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
