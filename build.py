import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent
ENTRY_POINT = "main.py"
EXE_NAME = "yacsp"
ICON_PATH = "resources/icon.ico"

INCLUDE_PACKAGES = [
  "PyQt6",
  "onnxruntime",
  "src",
  "autoit",
  "steam",
  "steam.utils",
  "steam.models",
  "steam.media",
  "google.protobuf",
]

RESOURCE_DATA = [
  ("src", "src"),
  ("resources", "resources"),
]


def build_executable():
  print("--- Starting Nuitka Build Process ---")

  if not Path(ENTRY_POINT).exists():
    print(f"[ERROR] Entry point {ENTRY_POINT} not found.")
    sys.exit(1)

  cmd = [
    sys.executable,
    "-m",
    "nuitka",
    "--onefile",
    "--standalone",
    f"--windows-icon-from-ico={PROJECT_ROOT / ICON_PATH}",
    "--plugin-enable=pyqt6",
    f"--output-filename={EXE_NAME}",
    "--windows-console-mode=attach",
  ]

  if False:
    # this shit takes time from the moon to the earth
    cmd.append("--lto=yes")

  for pkg in INCLUDE_PACKAGES:
    cmd.append(f"--include-package={pkg}")

  for source, dest in RESOURCE_DATA:
    full_source_path = PROJECT_ROOT / source
    if not full_source_path.exists():
      print(
        f"[WARNING] Resource folder not found: {full_source_path}. Skipping."
      )
      continue

    cmd.append(f"--include-data-dir={full_source_path}={dest}")

  cmd.append(ENTRY_POINT)

  print(f"[INFO] Nuitka command: {' '.join(cmd[:15])}...")

  try:
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
    print("\n--- Build SUCCESSFUL! ---")
    print(
      f"Executable is in: {PROJECT_ROOT / EXE_NAME}{'.exe' if sys.platform == 'win32' else ''}"
    )

  except subprocess.CalledProcessError as e:
    print("\n--- Build FAILED! ---")
    print(f"Nuitka exited with error code {e.returncode}.")
  except FileNotFoundError:
    print("\n--- Build FAILED! ---")
    print(
      "Error: Nuitka command not found. Please ensure Nuitka is installed (`uv run nuitka`)."
    )


if __name__ == "__main__":
  # update resources for every build
  subprocess.run(["uv", "run", "pack.py"])

  try:
    import nuitka
  except ImportError:
    print("Nuitka is not installed. Please run: uv run nuitka")
    sys.exit(1)

  build_executable()
