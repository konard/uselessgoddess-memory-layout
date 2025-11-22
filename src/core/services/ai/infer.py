from typing import List, Tuple, Optional

import time
import cv2
import numpy as np
import onnxruntime as ort

from dataclasses import dataclass
from core.logging import get_logger


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

  def encode(self) -> Tuple[int, float, float, float, float]:
    return (
      self.laidx,
      self.mid_x / self.input_x,
      self.mid_y / self.input_y,
      self.width / self.input_x,
      self.height / self.input_y,
    )

  def corners(self) -> Tuple[float, float]:
    return self.mid_x - self.width / 2, self.mid_x - self.height / 2


class InferenceService:
  def __init__(
    self,
    model_path: str,
    labels: List[str],
    conf_thres: float = 0.5,
    iou_thres: float = 0.45,
  ):
    self.labels = labels
    self.conf_thres = conf_thres
    self.iou_thres = iou_thres
    self.model_input_size = 320  # TODO: make prebuilt configurable

    self.session = self._init_session(model_path)

    self.input_name = self.session.get_inputs()[0].name
    self.output_name = self.session.get_outputs()[0].name

  def _init_session(self, model_path: str) -> ort.InferenceSession:
    providers = ort.get_available_providers()

    target_providers = []

    # DirectML -> CUDA -> CPU
    if "DmlExecutionProvider" in providers:
      target_providers.append("DmlExecutionProvider")
      logger.debug("DirectML detected (AMD/NVIDIA GPU acceleration enabled)")
    elif "CUDAExecutionProvider" in providers:
      target_providers.append("CUDAExecutionProvider")
      logger.debug("CUDA detected (NVIDIA GPU acceleration enabled)")

    target_providers.append("CPUExecutionProvider")

    try:
      session = ort.InferenceSession(model_path, providers=target_providers)
      logger.debug(f"Model loaded using providers: {session.get_providers()}")
      return session
    except Exception as e:
      logger.error(f"Failed to load model: {e}")
      raise e

  def preprocess(self, raw_frame: np.ndarray) -> np.ndarray:
    img = cv2.resize(raw_frame, (self.model_input_size, self.model_input_size))

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = img.transpose(2, 0, 1)
    img = np.expand_dims(img, 0)

    return img

  # non maximus suppression
  def _nms(self, boxes: np.ndarray, scores: np.ndarray) -> List[int]:
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
    self, output: np.ndarray, original_shape: Tuple[int, int]
  ) -> List[Target]:
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
      label_name = (
        self.labels[class_id] if class_id < len(self.labels) else str(class_id)
      )

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
      targets.append(target)

    return targets

  def infer(self, frame: np.ndarray) -> List[Target]:
    input_tensor = self.preprocess(frame)

    outputs = self.session.run(
      [self.output_name], {self.input_name: input_tensor}
    )

    return self.postprocess(outputs[0], frame.shape)
