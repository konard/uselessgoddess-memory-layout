import enum
import random
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
import win32api
import win32con

from core.logging import get_logger
from core.services.ai import Target, InferenceService
from core.keys import Key

from .config import config
from .detector import MinimapDirectionDetector
from .rotation import rotate_step
from .utils import Action, Context, Step

from core.services.ai.tracker import ByteTracker

logger = get_logger("match.aim")


def choose_target(
  targets: List[Target], center: Tuple[float, float]
) -> Optional[Target]:
  if not targets:
    return None
  if config.center_of_screen:
    cx, cy = center
    targets = sorted(
      targets,
      key=lambda t: (t.mid_x - cx) ** 2 + (t.mid_y - cy) ** 2,
    )
  # Note: original code computed a distance to last_mid_coord but never applied the sort
  return targets[0]


def compute_mouse_move(
  target: Target, center: Tuple[float, float], headshot: bool
) -> Tuple[float, float]:
  cx, cy = center
  box_height = target.height
  headshot_offset = box_height * (0.38 if headshot else 0.2)
  return target.mid_x - cx, (target.mid_y - headshot_offset) - cy


def maybe_move_mouse(dx: float, dy: float) -> None:
  win32api.mouse_event(
    win32con.MOUSEEVENTF_MOVE,
    int(dx * config.aa_movement_amp / model_multiplier),
    int(dy * config.aa_movement_amp / model_multiplier),
    0,
    0,
  )


def shoot_mouse() -> None:
  win32api.keybd_event(Key.K.value, 0, 0, 0)
  time.sleep(float(random.randint(60, 120)) / 10000)
  win32api.keybd_event(Key.K.value, 0, win32con.KEYEVENTF_KEYUP, 0)
  time.sleep(float(random.randint(60, 120)) / 10000)


def should_shoot(target: Target, center: Tuple[float, float]) -> bool:
  cx, cy = center
  distance = ((target.mid_x - cx) ** 2 + (target.mid_y - cy) ** 2) ** 0.5
  return distance <= config.shoot_distance_threshold


class State(enum.IntEnum):
  manual = 0
  align = 1
  walk = 2
  aim = 3


class FramesTimer:
  def __init__(self, duration: int):
    self.frames = 0
    self.duration = duration

  def tick(self):
    self.frames += 1

    if self.frames > self.duration:
      self.frames = 0
      return True
    else:
      return False


class Timer:
  def __init__(self, duration: float):
    self.time = 0
    self.duration = duration

  def stop(self):
    self.duration = float("inf")

  def tick(self, delta: float):
    self.time += delta

    if self.time > self.duration:
      self.time = 0
      return True
    else:
      return False


class CpsMonitor:
  def __init__(self):
    self.frames = 0
    self.time = 0

  def tick(self, delta: float):
    self.frames += 1
    self.time += delta

    if self.time >= 1.0:
      self.time = 0
      self.frames = 0
      self.time = 0


def filter_by_aspect(
  aspect_filter: float, targets: List[Target]
) -> List[Target]:
  filtered = []
  for t in targets:
    if t.height > 0:
      aspect = t.width / t.height
      if aspect <= aspect_filter:
        filtered.append(t)

  return filtered


model_multiplier = 3  # TODO: research

Kp = 0.4 * 6 / model_multiplier
Kd = 0.2 * 6 / model_multiplier


class AimController(Action):
  def __init__(self, direction: float, burst: bool = True):
    self.center = (config.screenshot_width // 2, config.screenshot_height // 2)
    self.monitor = CpsMonitor()

    self.direction = direction
    self.burst = burst

    # timers
    self.model_timer = FramesTimer(model_multiplier)
    self.burst_timer = Timer(0)
    self.pistol_timer = Timer(0)
    self.cooldown_timer = Timer(0)
    self.rotation_timer = Timer(0)

    self.last_known_target: Optional[Target] = None
    self.grace_timer = Timer(config.target_persistence)

    self.targets = []
    self.target = None
    # try to hs on this round
    self.headshot = random.random() < config.headshot_chance

    # persistent
    self.last_error_x = 0
    self.last_error_y = 0

    self.tracker = ByteTracker(track_thresh=0.5, match_thresh=0.8)
    self.locked_track_id = None

  def execute(self, ctx: Context) -> Step:
    self.step(
      ctx.team.enemy().label(),
      ctx.frame,
      ctx.model,
      ctx.delta,
      headshot=self.headshot,
    )
    return False, None

  def release(self):
    pass

  def step(
    self,
    enemy_label: str,
    frame,
    model,
    delta: float,
    headshot=False,
  ):
    targets = model.infer(frame)

    raw_targets = [t for t in targets if t.label == enemy_label]
    tracked_targets = self.tracker.update(raw_targets)

    # targets = filter_by_aspect(config.filter_aspect, targets)

    current_target = None
    if self.locked_track_id is not None:
      for t in tracked_targets:
        if getattr(t, "track_id", -1) == self.locked_track_id:
          current_target = t
          break

    if current_target is None:
      if tracked_targets:
        current_target = choose_target(tracked_targets, self.center)
        if current_target:
          self.locked_track_id = getattr(current_target, "track_id", None)

    # if self.model_timer.tick():
    #   self.targets = targets
    #   self.target = choose_target(self.targets, self.center)

    if current_target is not None:
      self.last_known_target = current_target
      self.grace_timer = Timer(config.target_persistence)
    else:
      if self.last_known_target is not None and not self.grace_timer.tick(
        delta
      ):
        current_target = self.last_known_target
      else:
        self.last_known_target = None
        self.locked_track_id = None

    self.target = current_target

    if self.target is not None:
      target_x = self.target.mid_x
      target_y = self.target.mid_y

      cx, cy = self.center

      box_height = self.target.height
      headshot_offset = box_height * (0.38 if headshot else 0.2)
      aim_y = target_y - headshot_offset

      error_x = target_x - cx
      error_y = aim_y - cy

      move_x = (error_x * Kp) + ((error_x - self.last_error_x) * Kd)
      move_y = (error_y * Kp) + ((error_y - self.last_error_y) * Kd)

      self.last_error_x = error_x
      self.last_error_y = error_y

      if abs(move_x) < 1.0:
        move_x = 0
      if abs(move_y) < 1.0:
        move_y = 0

      if move_x != 0 or move_y != 0:
        maybe_move_mouse(move_x, move_y)

      self.burst_fire(
        should_shoot(self.target, self.center),
        delta,
      )

      self.rotation_timer = Timer(config.rotation_interval)
    else:
      if config.enable_rotation:
        should_force_rotate = self.rotation_timer.tick(delta)

        if should_force_rotate:
          self.rotation_timer = Timer(0)
          # logger.debug("force rotating to search for targets")

        if len(self.targets) != 0:
          self.rotation_timer = Timer(config.rotation_interval)

        if should_force_rotate and len(self.targets) == 0:
          # todo rework rotation config values
          rotate_step(self.direction * 400 * delta)

    self.monitor.tick(delta)

  # todo!> use custom up/down functions instead of winapi
  def burst_fire(self, in_sight: bool, delta: float):
    shoot = Key.K.value

    if not in_sight:
      win32api.keybd_event(shoot, 0, win32con.KEYEVENTF_KEYUP, 0)
      return

    if not self.burst and self.pistol_timer.tick(delta):
      # todo!> extract uniform timer and shoot into function
      a, b = config.shoot_cooldown
      self.pistol_timer = Timer(random.uniform(a, b))
      win32api.keybd_event(shoot, 0, 0, 0)
      win32api.keybd_event(shoot, 0, win32con.KEYEVENTF_KEYUP, 0)
      return

    if self.burst_timer.tick(delta):
      win32api.keybd_event(shoot, 0, win32con.KEYEVENTF_KEYUP, 0)
      a, b = config.shoot_cooldown
      self.cooldown_timer = Timer(random.uniform(a, b))
      self.burst_timer.stop()
    elif self.cooldown_timer.tick(delta):
      win32api.keybd_event(shoot, 0, 0, 0)
      a, b = config.shoot_burst
      self.burst_timer = Timer(random.uniform(a, b))
      self.cooldown_timer.stop()
