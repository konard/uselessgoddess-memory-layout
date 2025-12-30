import math
import random
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

sys.path.append(str(Path(__file__).parents[1] / "src"))

from core.services.ai import InferenceService
from states.match.impl.aim import AimController
from states.match.impl.config import config

SENSITIVITY = 1
MODEL_INPUT_SIZE = getattr(config, "model_input", 320)


class VirtualCursor:
  def __init__(self, width, height):
    self.x = width // 2
    self.y = height // 2
    self.w = width
    self.h = height

  def move(self, dx, dy):
    self.x += dx
    self.y += dy
    self.x = max(0, min(self.w, self.x))
    self.y = max(0, min(self.h, self.y))


class MovingTarget:
  def __init__(self, w, h, sprite_path):
    self.w = w
    self.h = h
    self.t = 0
    self.sprite = cv2.imread(sprite_path)
    if self.sprite is None:
      self.sprite = np.zeros((60, 30, 3), dtype=np.uint8)
      self.sprite[:] = (0, 0, 255)
      self.sprite[0:15, :] = (0, 255, 255)
    else:
      self.sprite = cv2.resize(self.sprite, (75, 100))

    self.sw, self.sh = self.sprite.shape[1], self.sprite.shape[0]

    self.visible = True
    self.flicker_enabled = False
    self.flicker_timer = 0

  def update(self, mode="circle"):
    self.t += 0.03

    if self.flicker_enabled:
      self.flicker_timer -= 1
      if self.flicker_timer <= 0:
        self.visible = not self.visible
        if self.visible:
          self.flicker_timer = random.randint(30, 90)
        else:
          self.flicker_timer = random.randint(5, 20)
    else:
      self.visible = True

  def get_pos(self, mode="circle"):
    center_x, center_y = self.w // 2, self.h // 2

    if mode == "circle":
      radius = 200
      x = center_x + int(radius * math.cos(self.t))
      y = center_y + int(radius * math.sin(self.t))
    elif mode == "strafe":
      x = center_x + int(250 * math.sin(self.t * 1.2))
      y = center_y + int(50 * math.cos(self.t * 0.5))
    elif mode == "jiggle":
      x = center_x + int(60 * math.sin(self.t * 6))
      y = center_y
    else:
      x, y = center_x, center_y

    return x, y

  def draw(self, frame, x, y, force_ghost=False):
    x1 = int(x - self.sw // 2)
    y1 = int(y - self.sh // 2)
    x2 = x1 + self.sw
    y2 = y1 + self.sh

    h, w = frame.shape[:2]
    x1_c, y1_c = max(0, x1), max(0, y1)
    x2_c, y2_c = min(w, x2), min(h, y2)

    sp_x1 = x1_c - x1
    sp_y1 = y1_c - y1
    sp_x2 = sp_x1 + (x2_c - x1_c)
    sp_y2 = sp_y1 + (y2_c - y1_c)

    if sp_x2 > self.sw or sp_y2 > self.sh or x2_c <= x1_c or y2_c <= y1_c:
      return None

    sprite_part = self.sprite[sp_y1:sp_y2, sp_x1:sp_x2]
    bg_part = frame[y1_c:y2_c, x1_c:x2_c]

    if force_ghost:
      blended = cv2.addWeighted(bg_part, 0.5, sprite_part, 0.5, 0)
      frame[y1_c:y2_c, x1_c:x2_c] = blended
    else:
      frame[y1_c:y2_c, x1_c:x2_c] = sprite_part

    return (x1, y1, x2, y2)


def run_benchmark():
  W, H = 800, 600

  print(f"[INIT] AI Model: {MODEL_INPUT_SIZE}x{MODEL_INPUT_SIZE}")
  ai = InferenceService("model.onnx", ["ct", "t"])
  aim = AimController(direction=0, burst=False)

  v_mouse = VirtualCursor(W, H)
  target_gen = MovingTarget(W, H, "resources/enemy.png")

  trail = deque(maxlen=50)

  def mock_move(dx, dy):
    v_mouse.move(dx * SENSITIVITY, dy * SENSITIVITY)

  import states.match.impl.aim as aim_module

  aim_module.maybe_move_mouse = mock_move

  bg_grid = np.zeros((H, W, 3), dtype=np.uint8)
  for y in range(0, H, 50):
    color = (40, 40, 40) if y % 100 != 0 else (60, 60, 60)
    cv2.line(bg_grid, (0, y), (W, y), color, 1)
  for x in range(0, W, 50):
    color = (40, 40, 40) if x % 100 != 0 else (60, 60, 60)
    cv2.line(bg_grid, (x, 0), (x, H), color, 1)

  mode = "circle"
  manual_hide = False

  print("--- ULTIMATE AIM BENCHMARK ---")
  print(" [1-3] Movement Modes")
  print(" [F]   Toggle Auto-Flicker (Simulate bad neural network)")
  print(" [SPC] Hold to Hide Target (Simulate wall)")
  print(" [Q]   Quit")

  while True:
    target_gen.update(mode)
    tx, ty = target_gen.get_pos(mode)

    is_visible_for_ai = target_gen.visible and not manual_hide

    frame_ai_clean = bg_grid.copy()

    if is_visible_for_ai:
      target_gen.draw(frame_ai_clean, tx, ty, force_ghost=False)

    aim.center = (v_mouse.x, v_mouse.y)
    aim.step("ct", frame_ai_clean, ai, delta=(1 / 180))

    targets = ai.infer(frame_ai_clean)

    display_frame = frame_ai_clean.copy()

    if not is_visible_for_ai:
      target_gen.draw(display_frame, tx, ty, force_ghost=True)

    mx, my = int(v_mouse.x), int(v_mouse.y)

    trail.append((mx, my))
    for i in range(1, len(trail)):
      intensity = int(255 * (i / len(trail)))
      cv2.line(display_frame, trail[i - 1], trail[i], (0, intensity, 0), 2)

    for t in targets:
      x1 = int(t.mid_x - t.width / 2)
      y1 = int(t.mid_y - t.height / 2)
      cv2.rectangle(
        display_frame,
        (x1, y1),
        (x1 + int(t.width), y1 + int(t.height)),
        (0, 255, 255),
        1,
      )

    cv2.line(display_frame, (mx, my), (int(tx), int(ty)), (50, 50, 50), 1)

    cross_color = (0, 255, 0)  # Green (Default)
    status_text = "SEARCHING"
    status_color = (255, 255, 255)

    if aim.target:
      if is_visible_for_ai:
        status_text = "LOCKED (LIVE)"
        status_color = (0, 255, 0)
        cross_color = (0, 255, 0)
      else:
        status_text = "LOCKED (MEMORY)"
        status_color = (0, 255, 255)
        cross_color = (0, 255, 255)
    else:
      status_text = "SEARCHING"
      status_color = (0, 0, 255)
      cross_color = (0, 0, 255)

    cv2.line(display_frame, (mx - 20, my), (mx + 20, my), cross_color, 2)
    cv2.line(display_frame, (mx, my - 20), (mx, my + 20), cross_color, 2)
    cv2.circle(display_frame, (mx, my), 3, cross_color, -1)

    y_off = 30

    def draw_ui(text, col=(200, 200, 200)):
      nonlocal y_off
      cv2.putText(display_frame, text, (10, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
      y_off += 25

    draw_ui(f"Status: {status_text}", status_color)

    dist = math.sqrt((tx - mx) ** 2 + (ty - my) ** 2)
    draw_ui(f"Error:  {dist:.1f} px")
    draw_ui(f"Mode:   {mode}")

    flicker_state = "ON" if target_gen.flicker_enabled else "OFF"
    draw_ui(
      f"Flicker: {flicker_state} [F]",
      (100, 255, 100) if target_gen.flicker_enabled else (100, 100, 100),
    )

    if manual_hide:
      draw_ui("HIDDEN [Space]", (0, 0, 255))

    ai_debug = cv2.resize(frame_ai_clean, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
    cv2.imshow("AI Input", ai_debug)

    cv2.imshow("Aim Sandbox", display_frame)

    key = cv2.waitKey(1)
    if key & 0xFF == ord("q"):
      break
    if key & 0xFF == ord("1"):
      mode = "circle"
      trail.clear()
    if key & 0xFF == ord("2"):
      mode = "strafe"
      trail.clear()
    if key & 0xFF == ord("3"):
      mode = "jiggle"
      trail.clear()
    if key & 0xFF == ord("f"):
      target_gen.flicker_enabled = not target_gen.flicker_enabled

    import win32api

    manual_hide = win32api.GetKeyState(0x20) < 0  # 0x20 = VK_SPACE

  cv2.destroyAllWindows()


if __name__ == "__main__":
  run_benchmark()
