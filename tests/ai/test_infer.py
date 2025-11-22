import pytest
import cv2
import numpy as np
import os

from core.services.ai import InferenceService, Target

LABELS = ["ct", "t"]


@pytest.fixture(scope="module")
def service(model_path):
  if not model_path.exists():
    pytest.skip(f"Model not found at {model_path}", allow_module_level=True)

  try:
    return InferenceService(str(model_path), LABELS)
  except Exception as e:
    pytest.skip(f"Failed to init ONNX: {e}", allow_module_level=True)


@pytest.fixture(scope="module")
def test_image(test_image_path):
  if test_image_path.exists():
    print(f"Loaded real image: {test_image_path}")
    return cv2.imread(str(test_image_path))
  else:
    print("Generating random noise")
    return np.random.randint(0, 255, (320, 320, 3), dtype=np.uint8)


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
