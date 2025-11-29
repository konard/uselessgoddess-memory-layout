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
    self._init_camera()

  def _init_camera(self):
    self.camera = bettercam.create(output_idx=0, output_color="BGRA")
    self.w = self.camera.width
    self.h = self.camera.height

  def capture(self, region: Region = None) -> np.ndarray:
    if self.camera is None:
      self._init_camera()

    if region:  # record sizes
      rect = region
    else:
      rect = self

    if region:
      region = (
        region.x,
        region.y,
        region.x + region.w,
        region.y + region.h,
      )

    frame = self.camera.grab(region=region)

    if frame is None:
      return np.zeros((rect.h, rect.w, 3), dtype=np.uint8)

    return frame

  def release(self):
    self.camera = None
