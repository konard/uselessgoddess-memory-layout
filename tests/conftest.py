from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def model_path():
  return "model.onnx"


@pytest.fixture(scope="session")
def test_image_path():
  return "infer.png"
