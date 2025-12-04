import onnxruntime  # FIXME: RESEARCH ONNX import problem

import pytest
import cv2
import numpy as np

from core.services.ai import InferenceService, Target
import resources


def test_scale():
  target = Target(
    input_x=640,
    input_y=640,
    mid_x=320,
    mid_y=320,
    width=160,
    height=160,
    confidence=0.95,
    label="",
    laidx=0,
  )

  assert target == target.scale_to(1, 1).scale_to(640, 640)

  scaled = Target(
    360, 270, 180, 135, 90, 67.5, confidence=0.95, label="", laidx=0
  )
  assert scaled == target.scale_to(360, 270)


LABELS = ["ct", "t"]


@pytest.fixture(scope="module")
def service(model_path):
  try:
    return InferenceService(str(model_path), LABELS)
  except Exception as e:
    pytest.skip(f"Failed to init ONNX: {e}", allow_module_level=True)


@pytest.fixture(scope="module")
def test_image(test_image_path):
  print(f"Loaded real image: {test_image_path}")
  np_bytes = np.frombuffer(resources.load(test_image_path), dtype=np.uint8)
  return cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)


def test_provider_selection(service):
  providers = service.session.get_providers()
  print(f"\nActive ONNX Providers: {providers}")

  assert len(providers) > 0

  if "CPUExecutionProvider" == providers[0] and len(providers) == 1:
    pytest.warns(UserWarning, match="Running on CPU only")


def test_inference_structure(service, test_image):
  targets = service.infer(test_image)

  assert isinstance(targets, list)

  if targets:
    t = targets[0]
    assert isinstance(t, Target)
    assert 0 <= t.confidence <= 1.0
    assert t.label in LABELS


def test_benchmark_fps(service, test_image):
  import time

  iterations = 50

  for _ in range(10):  # warmup
    service.infer(test_image)

  start_time = time.time()
  for _ in range(iterations):
    targets = service.infer(test_image)
    assert len(targets) >= 1
  total_time = time.time() - start_time

  fps = iterations / total_time

  print(f"\nRESULT: {fps:.2f} FPS")
  assert fps > 1.0, "Inference is too slow!"
