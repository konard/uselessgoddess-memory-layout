import cv2
import numpy as np
from typing import Optional
from dataclasses import dataclass
import math


@dataclass
class MinimapConfig:
  scale: int = 1
  x: int = 97
  y: int = 97
  radius: int = 42
  threshold: int = 180


class MinimapDirectionDetector:
  def __init__(self, config: MinimapConfig):
    self.config = config

  def extract_rotation(
    self, frame: np.ndarray, visuals=False
  ) -> Optional[float]:
    height, width = frame.shape[:2]
    x = min(width, self.config.x)
    y = min(height, self.config.y)

    frame = frame[0:y, 0:x].copy()
    frame = cv2.resize(
      frame, (x * self.config.scale, y * self.config.scale), cv2.INTER_CUBIC
    )
    height, width = frame.shape[:2]
    center_x, center_y = width // 2, height // 2

    roi_radius = 10

    x1 = center_x - roi_radius
    y1 = center_y - roi_radius
    x2 = center_x + roi_radius
    y2 = center_y + roi_radius

    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
      return None

    roi = frame[y1:y2, x1:x2]

    scale_factor = 16
    roi_big = cv2.resize(
      roi,
      (0, 0),
      fx=scale_factor,
      fy=scale_factor,
      interpolation=cv2.INTER_LANCZOS4,
    )

    gray = cv2.cvtColor(roi_big, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, self.config.threshold, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(
      mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if visuals:
      cv2.imshow("ROI", roi_big)

    if not contours:
      return None

    arrow_contour = max(contours, key=cv2.contourArea)
    if visuals:
      debug_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
      cv2.drawContours(debug_img, [arrow_contour], -1, (0, 255, 0), 1)
      cv2.imshow("Detector Logic", debug_img)

    if cv2.contourArea(arrow_contour) < 500:
      return None

    h_big, w_big = roi_big.shape[:2]
    center_big_x, center_big_y = w_big // 2, h_big // 2

    max_dist = 0
    nose_point = None

    for point in arrow_contour:
      px, py = point[0]
      dist = (px - center_big_x) ** 2 + (py - center_big_y) ** 2

      if dist > max_dist:
        max_dist = dist
        nose_point = (px, py)

    if nose_point is None:
      return None

    dy = nose_point[1] - center_big_y
    dx = nose_point[0] - center_big_x

    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)

    # correction
    final_angle = angle_deg + 180

    final_angle = (final_angle + 360) % 360

    return final_angle
