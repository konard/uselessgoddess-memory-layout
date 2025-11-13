from __future__ import annotations

import os
import sys
import asyncio
import qasync
import subprocess
from pyuac import main_requires_admin

from PyQt6.QtWidgets import QApplication

from src.app.main_window import MainWindow
from src.states import Idle
import pyautogui

pyautogui.FAILSAFE = False


@main_requires_admin
async def main():
  _app = QApplication.instance() or QApplication(sys.argv)

  window = MainWindow()
  window.show()

  await window.manager.into_state(Idle())

  await asyncio.get_event_loop().create_future()


def dev_deps():
  NODE_DIR = os.path.join(os.path.dirname(__file__), "resources", "scripts")
  NODE_MODULES_DIR = os.path.join(NODE_DIR, "node_modules")

  if not os.path.exists(NODE_MODULES_DIR):
    try:
      print("[*] installing scripts dependencies...")
      subprocess.run(["npm.cmd", "install"], cwd=NODE_DIR, check=True)
    except subprocess.CalledProcessError:
      sys.exit(1)
  print("[+] scripts dependencies installed")


if __name__ == "__main__":
  dev_deps()

  try:
    qasync.run(main())
  except asyncio.CancelledError:
    pass
