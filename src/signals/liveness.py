"""A lightweight active blink challenge used before identity enrollment.

This is not a claim of presentation-attack-proof biometrics.  It blocks the
most basic printed-photo attack by requiring an open -> closed -> open eye
sequence observed across multiple frames before monitoring can begin.
"""
from __future__ import annotations

from enum import Enum

from src.perception.perception_result import PerceptionResult

from .eye_state import calculate_eye_aspect_ratios


class BlinkChallengeState(str, Enum):
    WAITING_OPEN = "WAITING_OPEN"
    WAITING_CLOSED = "WAITING_CLOSED"
    WAITING_REOPEN = "WAITING_REOPEN"
    VERIFIED = "VERIFIED"


class BlinkLivenessChallenge:
    def __init__(
        self,
        ear_threshold: float = 0.21,
        min_open_frames: int = 2,
        min_closed_frames: int = 2,
    ) -> None:
        if ear_threshold <= 0 or min_open_frames <= 0 or min_closed_frames <= 0:
            raise ValueError("Tham so blink liveness phai duong")
        self._ear_threshold = ear_threshold
        self._min_open_frames = min_open_frames
        self._min_closed_frames = min_closed_frames
        self.reset()

    def reset(self) -> None:
        self.state = BlinkChallengeState.WAITING_OPEN
        self._consecutive_frames = 0

    @property
    def verified(self) -> bool:
        return self.state is BlinkChallengeState.VERIFIED

    @property
    def prompt(self) -> str:
        if self.state is BlinkChallengeState.WAITING_OPEN:
            return "Nhin thang camera"
        if self.state is BlinkChallengeState.WAITING_CLOSED:
            return "Hay nham ca hai mat"
        if self.state is BlinkChallengeState.WAITING_REOPEN:
            return "Mo mat tro lai"
        return "Kiem tra song da dat"

    def update(self, result: PerceptionResult) -> bool:
        if self.verified:
            return True
        if result.face_landmarks is None:
            self._consecutive_frames = 0
            return False

        ear_left, ear_right = calculate_eye_aspect_ratios(
            result.face_landmarks, result.frame_shape,
        )
        both_open = ear_left >= self._ear_threshold and ear_right >= self._ear_threshold
        both_closed = ear_left < self._ear_threshold and ear_right < self._ear_threshold

        expected = both_closed if self.state is BlinkChallengeState.WAITING_CLOSED else both_open
        self._consecutive_frames = self._consecutive_frames + 1 if expected else 0

        threshold = (
            self._min_closed_frames
            if self.state is BlinkChallengeState.WAITING_CLOSED
            else self._min_open_frames
        )
        if self._consecutive_frames < threshold:
            return False

        self._consecutive_frames = 0
        if self.state is BlinkChallengeState.WAITING_OPEN:
            self.state = BlinkChallengeState.WAITING_CLOSED
        elif self.state is BlinkChallengeState.WAITING_CLOSED:
            self.state = BlinkChallengeState.WAITING_REOPEN
        else:
            self.state = BlinkChallengeState.VERIFIED
        return self.verified
