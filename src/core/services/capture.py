import bettercam
import numpy as np
from dataclasses import dataclass
from core.logging import get_logger
import ctypes

logger = get_logger("sv.capture")


def get_screen_resolution() -> tuple[int, int]:
  try:
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w, h
  except Exception:
    import tkinter

    root = tkinter.Tk()
    return root.winfo_screenwidth(), root.winfo_screenheight()


@dataclass
class Region:
  x: int
  y: int
  w: int
  h: int


class ScreenCaptureService:
  def __init__(self):
    self.camera = None
    self._last_valid_frame = None
    self._init_camera()

  def _init_camera(self):
    try:
      if self.camera is not None:
        self.camera.stop()

      self.camera = bettercam.create(output_idx=0, output_color="BGRA")

      self.camera.start(target_fps=120)

      self.w = self.camera.width
      self.h = self.camera.height
      logger.info(f"Camera initialized: {self.w}x{self.h}")
    except Exception as e:
      logger.error(f"Failed to init camera: {e}")
      self.camera = None

  def capture(self, region: Region = None) -> np.ndarray:
    if self.camera is None:
      self._init_camera()
      target_w = region.w if region else self.camera.width
      target_h = region.h if region else self.camera.height
      return np.zeros((target_h, target_w, 3), dtype=np.uint8)

    frame = self.camera.get_latest_frame()

    if frame is None:
      try:
        frame = self.camera.grab()
      except Exception:
        self.camera = None

    if frame is None:
      frame = self._last_valid_frame

    if frame is None:
      target_w = region.w if region else self.w
      target_h = region.h if region else self.h
      return np.zeros((target_h, target_w, 3), dtype=np.uint8)

    self._last_valid_frame = frame

    if region:
      x = max(0, region.x)
      y = max(0, region.y)

      cropped = frame[y : y + region.h, x : x + region.w]

      if cropped.size == 0:
        return np.zeros((region.h, region.w, 3), dtype=np.uint8)

      return cropped

    return frame

  def release(self):
    if self.camera:
      self.camera.stop()
      self.camera = None
    self._last_valid_frame = None
