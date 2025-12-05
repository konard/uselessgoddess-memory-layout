from __future__ import annotations

import onnxruntime as ort

import os
import sys
import asyncio
import qasync
import ctypes
import subprocess
from pyuac import isUserAdmin, runAsAdmin

# Add src to sys.path to allow imports from core, app, etc.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from states.idle import Idle
import pyautogui

from src.constants import IS_DEV_MODE

pyautogui.FAILSAFE = False


async def main():
  _app = QApplication.instance() or QApplication(sys.argv)

  window = MainWindow()
  window.show()

  await window.manager.into_state(Idle())

  await asyncio.get_event_loop().create_future()


def dev_deps():
  NODE_DIR = os.path.join("data", "scripts")
  NODE_MODULES_DIR = os.path.join(NODE_DIR, "node_modules")

  if not os.path.exists(NODE_MODULES_DIR):
    try:
      print("[*] installing scripts dependencies...")
      subprocess.run(["npm", "install"], cwd=NODE_DIR, check=True)
    except subprocess.CalledProcessError:
      sys.exit(1)
  print("[+] scripts dependencies installed")


def is_debugger_present():
  is_debugger = ctypes.c_bool(False)
  try:
    ctypes.windll.kernel32.CheckRemoteDebuggerPresent(
      ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(is_debugger)
    )
    return is_debugger.value
  except Exception:
    return False


if __name__ == "__main__":
  dev_deps()

  if IS_DEV_MODE:
    # we need fresh resources every run
    subprocess.run(["py", "pack.py"], check=True)
  else:
    if sys.stderr is None:
      sys.stderr = open(os.devnull, "w")
    if sys.stdout is None:
      sys.stdout = open(os.devnull, "w")

  # Проверяем права администратора и перезапускаем с правами админа, если нужно
  if not isUserAdmin():
    runAsAdmin()
    sys.exit(0)

  if is_debugger_present():
    sys.exit(0)

  try:
    qasync.run(main())
  except asyncio.CancelledError:
    pass
