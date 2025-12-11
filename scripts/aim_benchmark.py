import cv2
import numpy as np
import time
import math
import sys
from pathlib import Path
from collections import deque

sys.path.append(str(Path(__file__).parents[1] / "src"))

from core.services.ai import InferenceService
from states.match.impl.aim import AimController
from states.match.impl.config import config


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
      self.sprite = cv2.resize(self.sprite, (50, 80))

    self.sw, self.sh = self.sprite.shape[1], self.sprite.shape[0]

  def get_pos(self, mode="circle"):
    self.t += 0.03
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

  def draw(self, frame, x, y):
    x1 = int(x - self.sw // 2)
    y1 = int(y - self.sh // 2)
    x2 = x1 + self.sw
    y2 = y1 + self.sh

    h, w = frame.shape[:2]
    x1_c = max(0, x1)
    y1_c = max(0, y1)
    x2_c = min(w, x2)
    y2_c = min(h, y2)

    sp_x1 = x1_c - x1
    sp_y1 = y1_c - y1
    sp_x2 = sp_x1 + (x2_c - x1_c)
    sp_y2 = sp_y1 + (y2_c - y1_c)

    if sp_x2 > self.sw or sp_y2 > self.sh or x2_c <= x1_c or y2_c <= y1_c:
      return None

    _roi = frame[y1_c:y2_c, x1_c:x2_c]
    sprite_roi = self.sprite[sp_y1:sp_y2, sp_x1:sp_x2]

    frame[y1_c:y2_c, x1_c:x2_c] = sprite_roi
    return (x1, y1, x2, y2)


def run_benchmark():
  W, H = 800, 600

  print("[INIT] Loading AI...")
  ai = InferenceService("model.onnx", ["ct", "t"])

  aim = AimController(direction=0, burst=False)

  v_mouse = VirtualCursor(W, H)
  target_gen = MovingTarget(W, H, "resources/enemy.png")

  trail = deque(maxlen=50)

  def mock_move(dx, dy):
    scale = 0.5
    v_mouse.move(dx * scale, dy * scale)

  import states.match.impl.aim as aim_module

  aim_module.maybe_move_mouse = mock_move

  background = np.zeros((H, W, 3), dtype=np.uint8)
  for y in range(0, H, 100):
    cv2.line(background, (0, y), (W, y), (30, 30, 30), 1)
  for x in range(0, W, 100):
    cv2.line(background, (x, 0), (x, H), (30, 30, 30), 1)

  mode = "circle"

  print("--- 2D CURSOR BENCHMARK ---")
  print("Green Cross = Your Aim")
  print("Enemy = Target")
  print("Controls: [1] Circle [2] Strafe [3] Jiggle [Q] Quit")

  while True:
    frame = background.copy()

    tx, ty = target_gen.get_pos(mode)
    target_gen.draw(frame, tx, ty)

    targets = ai.infer(frame)

    aim.center = (v_mouse.x, v_mouse.y)

    aim.step("ct", targets, delta=0.016)

    mx, my = int(v_mouse.x), int(v_mouse.y)

    cv2.line(frame, (mx - 20, my), (mx + 20, my), (0, 255, 0), 2)
    cv2.line(frame, (mx, my - 20), (mx, my + 20), (0, 255, 0), 2)
    cv2.circle(frame, (mx, my), 2, (0, 255, 0), -1)

    cv2.line(frame, (mx, my), (int(tx), int(ty)), (0, 255, 255), 1)

    trail.append((mx, my))
    for i in range(1, len(trail)):
      cv2.line(frame, trail[i - 1], trail[i], (0, 100, 0), 1)

    for t in targets:
      x1 = int(t.mid_x - t.width / 2)
      y1 = int(t.mid_y - t.height / 2)
      cv2.rectangle(
        frame,
        (x1, y1),
        (x1 + int(t.width), y1 + int(t.height)),
        (100, 100, 100),
        1,
      )

    dist = math.sqrt((tx - mx) ** 2 + (ty - my) ** 2)
    cv2.putText(
      frame,
      f"Error: {dist:.1f} px",
      (10, 30),
      cv2.FONT_HERSHEY_SIMPLEX,
      0.7,
      (255, 255, 255),
      2,
    )
    cv2.putText(
      frame,
      f"Mode: {mode}",
      (10, 60),
      cv2.FONT_HERSHEY_SIMPLEX,
      0.7,
      (200, 200, 200),
      1,
    )

    cv2.imshow("Aim Sandbox", frame)

    key = cv2.waitKey(1)
    if key & 0xFF == ord("q"):
      break
    elif key & 0xFF == ord("1"):
      mode = "circle"
      trail.clear()
    elif key & 0xFF == ord("2"):
      mode = "strafe"
      trail.clear()
    elif key & 0xFF == ord("3"):
      mode = "jiggle"
      trail.clear()

  cv2.destroyAllWindows()


if __name__ == "__main__":
  run_benchmark()
