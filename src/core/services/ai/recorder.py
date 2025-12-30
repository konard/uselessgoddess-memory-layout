import queue
import threading
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from core.logging import get_logger

logger = get_logger("ai.recorder")


class DataRecorder:
  def __init__(self, save_path="data/dataset", active=False):
    self.active = active
    self.save_path = Path(save_path)
    self.images_path = self.save_path / "images"
    self.labels_path = self.save_path / "labels"

    self.queue = queue.Queue(maxsize=50)
    self._stop_event = threading.Event()
    self._thread = threading.Thread(
      target=self._worker, daemon=True, name="RecorderThread"
    )

    if self.active:
      self._init_dirs()
      self._thread.start()

  def _init_dirs(self):
    self.images_path.mkdir(parents=True, exist_ok=True)
    self.labels_path.mkdir(parents=True, exist_ok=True)

    classes_path = self.save_path / "classes.txt"
    if not classes_path.exists():
      with open(classes_path, "w") as f:
        f.write("ct\nt")

  def save(self, frame: np.ndarray, targets: list):
    if not self.active:
      return

    if self.queue.full():
      return

    self.queue.put((frame.copy(), targets))

  def _worker(self):
    logger.info("Dataset recorder started")
    while not self._stop_event.is_set():
      try:
        item = self.queue.get(timeout=1.0)
        frame, targets = item
      except queue.Empty:
        continue

      try:
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"

        if frame.shape[2] == 4:
          frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        img_name = f"{unique_id}.png"
        cv2.imwrite(str(self.images_path / img_name), frame)

        h, w = frame.shape[:2]

        txt_name = f"{unique_id}.txt"
        with open(self.labels_path / txt_name, "w") as f:
          for t in targets:
            nx = t.mid_x / w
            ny = t.mid_y / h
            nw = t.width / w
            nh = t.height / h

            f.write(f"{t.laidx} {nx:.6f} {ny:.6f} {nw:.6f} {nh:.6f}\n")

      except Exception as e:
        logger.error(f"Recorder write error: {e}")
      finally:
        self.queue.task_done()

  def stop(self):
    self._stop_event.set()
    if self._thread.is_alive():
      self._thread.join()
