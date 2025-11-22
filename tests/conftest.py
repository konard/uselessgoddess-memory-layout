import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def project_root():
  return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def model_path(project_root):
  return project_root / "resources" / "model.onnx"


@pytest.fixture(scope="session")
def test_image_path(project_root):
  return project_root / "resources" / "infer.png"
