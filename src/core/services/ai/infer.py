import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort

import resources
from core.logging import get_logger
from core.services.settings import InferenceDevice

from .recorder import DataRecorder

logger = get_logger("vis.infer")


@dataclass
class Target:
  input_x: int
  input_y: int
  mid_x: float
  mid_y: float
  width: float
  height: float
  confidence: float
  label: str
  laidx: int
  headshot: bool = False
  track_id: int = -1

  def scale_to(self, input_x: int, input_y: int):
    scale_x, scale_y = (input_x / self.input_x, input_y / self.input_y)
    return Target(
      input_x=input_x,
      input_y=input_y,
      mid_x=self.mid_x * scale_x,
      mid_y=self.mid_y * scale_y,
      width=self.width * scale_x,
      height=self.height * scale_y,
      confidence=self.confidence,
      label=self.label,
      laidx=self.laidx,
      headshot=self.headshot,
    )

  def encode(self) -> tuple[int, float, float, float, float]:
    return (
      self.laidx,
      self.mid_x / self.input_x,
      self.mid_y / self.input_y,
      self.width / self.input_x,
      self.height / self.input_y,
    )

  def corners(self) -> tuple[float, float]:
    return self.mid_x - self.width / 2, self.mid_x - self.height / 2


class InferenceService:
  def __init__(
    self,
    model_path: str,
    labels: list[str],
    device: InferenceDevice = InferenceDevice.CPU,
    threads: int = 1,
    conf_thres: float = 0.5,
    iou_thres: float = 0.45,
  ):
    self.labels = labels
    self.conf_thres = conf_thres
    self.iou_thres = iou_thres
    self.model_input_size = 320  # TODO: make prebuilt configurable

    self.model_path = model_path
    self.device = device
    self.threads = threads
    self.session = self._init_session(model_path, device, threads)

    self.input_name = self.session.get_inputs()[0].name
    self.output_name = self.session.get_outputs()[0].name
    self.recorder = DataRecorder(active=True)
    self.frame_counter = 0

  def _init_session(
    self, model_path: str, device: InferenceDevice, threads: int
  ) -> ort.InferenceSession:
    available = ort.get_available_providers()
    target_providers = []

    logger.debug(f"available providers: {available}")

    logger.info(f"Requested inference device: {device.value}")

    if device == InferenceDevice.GPU:
      # Priority: DirectML (AMD/NVIDIA/Intel on Windows) -> CUDA -> CPU
      if "DmlExecutionProvider" in available:
        target_providers.append("DmlExecutionProvider")
      elif "CUDAExecutionProvider" in available:
        target_providers.append("CUDAExecutionProvider")
      else:
        logger.warn(
          "GPU requested but no GPU provider found in ONNXRuntime. Falling back to CPU."
        )
        target_providers.append("CPUExecutionProvider")
    else:
      target_providers.append("CPUExecutionProvider")

    sess_options = ort.SessionOptions()
    if threads != 0:
      sess_options.intra_op_num_threads = threads
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    try:
      session = ort.InferenceSession(
        resources.load(model_path), providers=target_providers, sess_options=sess_options
      )
      logger.debug(f"Model loaded using: {session.get_providers()[0]}")
      return session
    except Exception as e:
      logger.error(f"Failed to load model: {e}")
      raise e

  def reload(self, device: InferenceDevice, threads: int):
    self.device = device
    self.threads = threads
    self.session = self._init_session(self.model_path, device, threads)

  def benchmark(self, iterations: int = 50) -> dict:
    dummy_frame = np.zeros(
      (self.model_input_size, self.model_input_size, 3), dtype=np.uint8
    )

    for _ in range(5):
      self.infer(dummy_frame)

    start_time = time.perf_counter()
    for _ in range(iterations):
      self.infer(dummy_frame)
    total_time = time.perf_counter() - start_time

    avg_latency_ms = (total_time / iterations) * 1000
    fps = iterations / total_time

    return {
      "provider": self.session.get_providers()[0],
      "latency_ms": round(avg_latency_ms, 2),
      "fps": round(fps, 1),
      "iterations": iterations,
    }

  def preprocess(self, raw_frame: np.ndarray) -> np.ndarray:
    img = cv2.resize(raw_frame, (self.model_input_size, self.model_input_size))

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = img.transpose(2, 0, 1)
    img = np.expand_dims(img, 0)

    return img

  # non maximus suppression
  def _nms(self, boxes: np.ndarray, scores: np.ndarray) -> list[int]:
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
      i = order[0]
      keep.append(i)

      xx1 = np.maximum(x1[i], x1[order[1:]])
      yy1 = np.maximum(y1[i], y1[order[1:]])
      xx2 = np.minimum(x2[i], x2[order[1:]])
      yy2 = np.minimum(y2[i], y2[order[1:]])

      w = np.maximum(0.0, xx2 - xx1)
      h = np.maximum(0.0, yy2 - yy1)
      inter = w * h
      ovr = inter / (areas[i] + areas[order[1:]] - inter)

      inds = np.where(ovr <= self.iou_thres)[0]
      order = order[inds + 1]

    return keep

  def postprocess(
    self, output: np.ndarray, original_shape: tuple[int, int]
  ) -> list[Target]:
    predictions = np.squeeze(output).T

    scores = np.max(predictions[:, 4:], axis=1)
    predictions = predictions[scores > self.conf_thres, :]
    scores = scores[scores > self.conf_thres]

    if len(scores) == 0:
      return []

    class_ids = np.argmax(predictions[:, 4:], axis=1)

    boxes = predictions[:, :4]

    nms_boxes = boxes.copy()
    nms_boxes[:, 0] = boxes[:, 0] - boxes[:, 2] / 2  # x1
    nms_boxes[:, 1] = boxes[:, 1] - boxes[:, 3] / 2  # y1
    nms_boxes[:, 2] = boxes[:, 0] + boxes[:, 2] / 2  # x2
    nms_boxes[:, 3] = boxes[:, 1] + boxes[:, 3] / 2  # y2

    indices = self._nms(nms_boxes, scores)

    targets = []
    orig_h, orig_w = original_shape[:2]

    for i in indices:
      cx, cy, w, h = boxes[i]
      score = scores[i]
      class_id = class_ids[i]
      label_name = self.labels[class_id] if class_id < len(self.labels) else str(class_id)

      target = Target(
        input_x=self.model_input_size,
        input_y=self.model_input_size,
        mid_x=float(cx),
        mid_y=float(cy),
        width=float(w),
        height=float(h),
        confidence=float(score),
        label=label_name,
        laidx=int(class_id),
      )
      targets.append(target.scale_to(orig_w, orig_h))

    return targets

  def infer(self, frame: np.ndarray) -> list[Target]:
    input_tensor = self.preprocess(frame)

    outputs = self.session.run([self.output_name], {self.input_name: input_tensor})

    targets = self.postprocess(outputs[0], frame.shape)

    if self.recorder.active:
      self.frame_counter += 1

      is_hard_example = any(0.35 < t.confidence < 0.75 for t in targets)
      is_interval = self.frame_counter % 60 == 0

      if is_interval and (is_hard_example or not targets):
        self.recorder.save(frame, targets)

    return targets
