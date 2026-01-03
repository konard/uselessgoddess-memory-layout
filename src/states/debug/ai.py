import asyncio
import threading
import time
from dataclasses import dataclass

import cv2
import pyautogui

from core.context import Context
from core.logging import get_logger
from core.panel import State
from core.services import Region  # TODO: move out from services
from ui.widgets import Button, Label

logger = get_logger("state.debug.ai")


class DebugWorker(threading.Thread):
  def __init__(self, ctx: Context):
    super().__init__(daemon=True)
    self.ctx = ctx
    self.running = True
    self.window_name = "YACS Debug AI (Press 'Q' to exit)"

  def run(self):
    logger.info("AI Debug Thread started")

    frame_count = 0
    start_time = time.time()
    fps = 0

    font = cv2.FONT_HERSHEY_SIMPLEX
    color_ct = (255, 0, 0)
    color_t = (0, 255, 255)
    color_cross = (0, 255, 0)

    while self.running:
      _loop_start = time.perf_counter()

      x, y = pyautogui.position()
      frame = self.ctx.screen.capture(Region(x, y, 320, 320))
      if frame is None:
        time.sleep(0.001)
        continue

      targets = self.ctx.ai.infer(frame)

      h, w = frame.shape[:2]
      cx, cy = w // 2, h // 2
      cv2.line(frame, (cx - 10, cy), (cx + 10, cy), color_cross, 1)
      cv2.line(frame, (cx, cy - 10), (cx, cy + 10), color_cross, 1)

      for t in targets:
        half_w = t.width * 0.5
        half_h = t.height * 0.5
        x1 = int(t.mid_x - half_w)
        y1 = int(t.mid_y - half_h)
        x2 = int(t.mid_x + half_w)
        y2 = int(t.mid_y + half_h)

        color = color_ct if t.label == "ct" else color_t

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        cv2.putText(frame, f"{t.confidence:.2f}", (x1, y1 - 5), font, 0.5, color, 1)

      frame_count += 1
      if frame_count % 10 == 0:
        elapsed = time.time() - start_time
        if elapsed > 0:
          fps = frame_count / elapsed
          if elapsed > 1.0:
            frame_count = 0
            start_time = time.time()

      cv2.putText(frame, f"FPS: {int(fps)}", (10, 30), font, 1, color_cross, 2)

      cv2.imshow(self.window_name, frame)

      if (cv2.waitKey(1) & 0xFF) == ord("q"):
        self.running = False

    cv2.destroyAllWindows()
    logger.info("AI Debug Thread stopped")


class AIState(State):
  def __init__(self):
    self.worker = None

  def layout(self, ctx: Context, dispatch):
    return [
      Label("AI Debug Mode Running..."),
      Label("Running in separate thread for MAX FPS."),
      Button(
        "Stop Debugging",
        on_click=lambda _: self.stop_signal(),
        button_type="DANGER",
      ),
    ]

  def stop_signal(self):
    if self.worker:
      self.worker.running = False

  async def execute(self, ctx: Context):
    self.worker = DebugWorker(ctx)
    self.worker.start()

    try:
      await asyncio.to_thread(self.worker.join)
    except asyncio.CancelledError:
      self.stop_signal()
      await asyncio.to_thread(self.worker.join)
      raise
