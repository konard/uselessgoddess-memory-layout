import cv2
import numpy as np
import time
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[1] / "src"))

from core.services.ai import InferenceService
from states.match.impl.aim import AimController
from states.match.impl.config import config


class VirtualMouse:
  def __init__(self, width, height):
    self.x = width // 2
    self.y = height // 2
    self.width = width
    self.height = height
    self.path = []

  def move(self, dx, dy):
    self.x += dx // 10
    self.y += dy // 10
    self.path.append((int(self.x), int(self.y)))
    if len(self.path) > 50:
      self.path.pop(0)


class MovingTarget:
  def __init__(self, w, h, sprite_path):
    self.w = w
    self.h = h
    self.t = 0
    self.sprite = cv2.imread(sprite_path)
    self.sprite = cv2.resize(self.sprite, (30, 60))
    if self.sprite is None:
      self.sprite = np.zeros((60, 30, 3), dtype=np.uint8)
      self.sprite[:] = (0, 0, 255)

    self.sw, self.sh = self.sprite.shape[1], self.sprite.shape[0]

  def get_pos(self, mode="circle"):
    self.t += 0.05 * 0.5
    center_x, center_y = self.w // 2, self.h // 2

    if mode == "circle":
      radius = 100
      x = center_x + int(radius * math.cos(self.t))
      y = center_y + int(radius * math.sin(self.t))
    elif mode == "strafe":
      x = center_x + int(150 * math.sin(self.t * 2))
      y = center_y
    elif mode == "jiggle":
      x = center_x + int(20 * math.sin(self.t * 10))
      y = center_y

    return x, y

  def draw(self, frame, x, y):
    x1 = int(x - self.sw // 2)
    y1 = int(y - self.sh // 2)
    x2 = x1 + self.sw
    y2 = y1 + self.sh

    if x1 < 0 or y1 < 0 or x2 >= self.w or y2 >= self.h:
      return frame

    _roi = frame[y1:y2, x1:x2]
    frame[y1:y2, x1:x2] = self.sprite
    return (x1, y1, x2, y2)


def run_benchmark():
  W, H = 360, 270

  ai = InferenceService("model.onnx", ["ct", "t"])
  aim = AimController(direction=0, burst=False)

  v_mouse = VirtualMouse(W, H)
  target_gen = MovingTarget(W, H, "resources/enemy.png")

  def mock_move(dx, dy):
    v_mouse.move(dx, dy)

  import states.match.impl.aim as aim_module

  aim_module.maybe_move_mouse = mock_move
  aim.center = (W // 2, H // 2)

  background = np.zeros((H, W, 3), dtype=np.uint8)

  print("Starting Benchmark. Press 'Q' to quit.")
  print("Modes: '1': Circle, '2': Strafe, '3': Jiggle")

  mode = "circle"

  while True:
    frame = background.copy()
    _start_time = time.perf_counter()

    tx, ty = target_gen.get_pos(mode)

    rel_tx = (W // 2) + (tx - v_mouse.x)
    rel_ty = (H // 2) + (ty - v_mouse.y)

    _target_box = target_gen.draw(frame, rel_tx, rel_ty)

    targets = ai.infer(frame)

    aim.step("ct", targets, delta=0.016)

    cv2.line(
      frame, (W // 2 - 10, H // 2), (W // 2 + 10, H // 2), (0, 255, 0), 1
    )
    cv2.line(
      frame, (W // 2, H // 2 - 10), (W // 2, H // 2 + 10), (0, 255, 0), 1
    )

    cv2.circle(frame, (int(rel_tx), int(rel_ty)), 3, (0, 0, 255), -1)

    error = math.sqrt((rel_tx - W // 2) ** 2 + (rel_ty - H // 2) ** 2)

    cv2.putText(
      frame,
      f"Error: {error:.2f} px",
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

    for t in targets:
      x1 = int(t.mid_x - t.width / 2)
      y1 = int(t.mid_y - t.height / 2)
      cv2.rectangle(
        frame,
        (x1, y1),
        (x1 + int(t.width), y1 + int(t.height)),
        (255, 255, 0),
        1,
      )

    cv2.imshow("Aim Benchmark", frame)

    key = cv2.waitKey(1)
    if key & 0xFF == ord("q"):
      break
    elif key & 0xFF == ord("1"):
      mode = "circle"
    elif key & 0xFF == ord("2"):
      mode = "strafe"
    elif key & 0xFF == ord("3"):
      mode = "jiggle"

  cv2.destroyAllWindows()


if __name__ == "__main__":
  run_benchmark()
