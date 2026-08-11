"""Shared typography values for the OpenCV user interface.

OpenCV's built-in text renderer uses scale factors instead of CSS-like pixel
sizes. Keeping the values here gives every overlay the same visual hierarchy.
"""
from __future__ import annotations

import cv2


FONT_FACE = cv2.FONT_HERSHEY_SIMPLEX

TEXT_SCALE_CAPTION = 0.55
TEXT_SCALE_BODY = 0.62
TEXT_SCALE_LABEL = 0.7
TEXT_SCALE_HEADING = 0.86

TEXT_THICKNESS_REGULAR = 1
TEXT_THICKNESS_EMPHASIS = 2
TEXT_LINE_HEIGHT = 22

