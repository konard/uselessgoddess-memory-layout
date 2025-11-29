import cv2
import numpy as np
from typing import Optional
from dataclasses import dataclass
import math


@dataclass
class MinimapConfig:
  scale: int = 2
  x: int = 97
  y: int = 97
  radius: int = 42
  threshold: int = 230


class MinimapDirectionDetector:
  def __init__(self, config: MinimapConfig):
    self.config = config

  def extract_rotation(
    self, frame: np.ndarray, visuals=False
  ) -> Optional[float]:
    height, width = frame.shape[:2]

    x = min(width, self.config.x)
    y = min(height, self.config.y)

    minimap = frame[0:y, 0:x].copy()
    minimap = cv2.resize(
      minimap, (x * self.config.scale, y * self.config.scale), cv2.INTER_CUBIC
    )

    h, w = minimap.shape[:2]
    center = (w // 2, h // 2)

    minimap = cv2.circle(
      minimap, center, self.config.radius * self.config.scale, 0, -1
    )

    white_mask = np.all(minimap > self.config.threshold, axis=-1)
    minimap[~white_mask] = [0, 0, 0, 0]

    pixels = np.argwhere(white_mask)
    pixels = sorted(pixels, key=lambda p: p[0] + p[1] + p[2])
    pixels.reverse()

    angle_position = None
    if len(pixels) > 0:
      angle_position = (int(pixels[0][1]), int(pixels[0][0]))

    angle = None
    if angle_position is not None:
      angle = math.atan2(
        angle_position[1] - center[1], angle_position[0] - center[0]
      )
      angle = angle * 180 / math.pi + 180

    if visuals:
      if angle is not None:
        minimap = cv2.line(minimap, center, angle_position, (0, 0, 255, 255), 2)
        # minimap = debug_label(minimap, f"{angle:.1f}", center)
      cv2.imshow("Minimap", minimap)

    return angle


def debug_label(image, label, center):
  text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
  font_face = (center[0] - text_size[0] // 2, center[1] + text_size[1] + 5)
  return cv2.putText(
    image,
    label,
    font_face,
    cv2.FONT_HERSHEY_SIMPLEX,
    0.6,
    (0, 255, 0, 255),
    2,
    cv2.LINE_AA,
  )
