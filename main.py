from __future__ import annotations

import asyncio
import contextlib
import ctypes
import os
import subprocess
import sys

import onnxruntime as ort
import qasync
from pyuac import isUserAdmin, runAsAdmin

# Add src to sys.path to allow imports from core, app, etc.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import urllib.request
from datetime import datetime

import pyautogui
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.license_dialog import LicenseInputDialog
from app.main_window import MainWindow
from core.services.license import LicenseKind
from src.constants import CHECK_LICENSE, IS_DEV_MODE
from src.core import license_old
from src.core.context import Context
from states.idle import Idle

pyautogui.FAILSAFE = False


async def bootstrap(app: QApplication):
  ctx = Context()

  if not ctx.su.license_key:
    dialog = LicenseInputDialog()
    if dialog.exec():
      ctx.lic.update_key(dialog.key)
      ctx.settings.save(ctx.settings.user)
    else:
      return None

  print("[Bootstrap] Verifying license...")

  asyncio.create_task(ctx.lic.start())

  for _ in range(30):
    if not CHECK_LICENSE:
      break
    if ctx.lic.state() == LicenseKind.VALID:
      break
    if ctx.lic.state() == LicenseKind.BANNED:
      QMessageBox.critical(None, "License Error", "License is banned or invalid.")
      return None
    if ctx.lic.state() == LicenseKind.PAUSED_LIMIT:
      QMessageBox.warning(None, "Limit Reached", "Session limit reached.")
      return None
    if ctx.lic.state() == LicenseKind.PAUSED_NETWORK:
      QMessageBox.warning(None, "Network error", "Check your connection.")
      return None

    await asyncio.sleep(0.5)
  else:
    QMessageBox.warning(
      None,
      "Network Error",
      """Could not connect to license server.
      Please check your connection!
      Or contact us (t.me/y_a_c_s_p)""",
    )
    return None

  return MainWindow(context=ctx)


async def main():
  app = QApplication.instance() or QApplication(sys.argv)
  app.setQuitOnLastWindowClosed(False)

  window = await bootstrap(app)
  if not window:
    sys.exit(0)
  window.show()

  await window.manager.into_state(Idle())

  should_close = asyncio.Event()
  app.lastWindowClosed.connect(should_close.set)
  await should_close.wait()


def dev_deps():
  pass


def is_debugger_present():
  is_debugger = ctypes.c_bool(False)
  try:
    ctypes.windll.kernel32.CheckRemoteDebuggerPresent(
      ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(is_debugger)
    )
    return is_debugger.value
  except Exception:
    return False


def is_admin():
  try:
    return ctypes.windll.shell32.IsUserAnAdmin()
  except Exception:
    return False


if __name__ == "__main__":
  dev_deps()

  if is_admin():
    print("Running as admin")

  if IS_DEV_MODE:
    from pathlib import Path

    # we need fresh resources every run
    subprocess.run(["py", "pack.py"], check=True)
    # TODO: `cs2_runner.exe` should be constant
    if not Path("cs2_runner.exe").exists():
      subprocess.run(["py", "build.py", "--runner"])
  else:
    sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115

  if IS_DEV_MODE and not isUserAdmin():
    runAsAdmin()
    sys.exit(0)

  if is_debugger_present():
    sys.exit(0)

  import ctypes

  # try:
  #   ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 10/11
  # except Exception:
  #   ctypes.windll.user32.SetProcessDPIAware()

  LIMIT_DAY = 17
  LIMIT_MONTH = 12
  LIMIT_YEAR = 2026

  license_old.check_expiration(datetime(LIMIT_YEAR, LIMIT_MONTH, LIMIT_DAY))

  with contextlib.suppress(asyncio.CancelledError):
    qasync.run(main())
