from typing import Optional

import win32api
import win32con

from .config import config


def smooth_rotate_to_target(current: float, target: float, speed: float) -> float | None:
  current_deg = current % 360
  target_deg = target % 360

  diff = (target_deg - current_deg + 360) % 360

  rotation_step = 50 * speed

  if abs(diff) < rotation_step:
    rotation_step = abs(diff)

  if diff > 180:
    move_x = int(rotation_step * config.aa_movement_amp)
  else:
    move_x = int(-rotation_step * config.aa_movement_amp)

  win32api.mouse_event(
    win32con.MOUSEEVENTF_MOVE,
    move_x,
    0,
    0,
    0,
  )

  return move_x


def rotate_step(speed: float) -> None:
  win32api.mouse_event(
    win32con.MOUSEEVENTF_MOVE,
    int(speed * config.aa_movement_amp),
    0,
    0,
    0,
  )
