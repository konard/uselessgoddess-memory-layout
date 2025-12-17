import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent
ENTRY_POINT = "main.py"
EXE_NAME = "yacsp"
ICON_PATH = "resources/icon.ico"

# use out src path
RUNNER_SCRIPT = "src/utils/cs_runner/cs2_runner.py"
RUNNER_EXE_NAME = "cs2_runner.exe"

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
  "selenium",
  "webdriver_manager",
  "cryptography",
]


def build_runner():
  print("--- Building CS2 Runner ---")

  runner_source = PROJECT_ROOT / RUNNER_SCRIPT
  if not runner_source.exists():
    print(f"[ERROR] Runner script not found at {runner_source}")
    sys.exit(1)

  output_exe = PROJECT_ROOT / RUNNER_EXE_NAME

  cmd = [
    sys.executable,
    "-m",
    "nuitka",
    "--onefile",
    "--standalone",
    f"--output-filename={output_exe}",
    "--windows-console-mode=disable",
    str(runner_source),
  ]

  print(f"[INFO] Runner build command: {' '.join(cmd)}")

  try:
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
    print(f"[SUCCESS] Runner compiled to: {output_exe}")
  except subprocess.CalledProcessError as e:
    print(f"[ERROR] Failed to build runner: {e}")
    sys.exit(1)


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
  parser = argparse.ArgumentParser(description="YACSP Build Tool")
  parser.add_argument(
    "--runner", action="store_true", help="Build ONLY the CS2 Runner"
  )
  parser.add_argument(
    "--main", action="store_true", help="Build ONLY the Main Application"
  )
  args = parser.parse_args()

  if args.runner:
    build_runner()
  elif args.main:
    subprocess.run(["py", "pack.py"], check=True)
    build_executable()
  else:
    subprocess.run(["py", "pack.py"], check=True)
    build_runner()
    build_executable()
