import os
import sys
import ctypes
import subprocess
import time
from pathlib import Path
from core.logging import get_logger

from constants import SANDBOX_PATH

logger = get_logger("sandbox")


class SandboxieInstaller:
  def __init__(self):
    logger.debug("init sandboxie installer")

    base_path = os.getcwd()
    if getattr(sys, "frozen", False):
      base_path = sys._MEIPASS
    elif __file__:
      base_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
      )

    self.sb_dir = os.path.join(base_path, SANDBOX_PATH)
    self.kmd_util = os.path.join(self.sb_dir, "KmdUtil.exe")
    self.start_exe = os.path.join(self.sb_dir, "Start.exe")

    self.drv_path = os.path.join(self.sb_dir, "SbieDrv.sys")
    self.svc_path = os.path.join(self.sb_dir, "SbieSvc.exe")
    self.msg_path = os.path.join(self.sb_dir, "SbieMsg.dll")

    logger.debug(f"sandbox dir: {self.sb_dir}")

  def is_service_running(self) -> bool:
    try:
      output = subprocess.check_output(
        ["sc", "query", "SbieSvc"],
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
      ).decode("oem", errors="ignore")
      return "RUNNING" in output
    except Exception:
      return False

  def is_driver_installed(self) -> bool:
    try:
      subprocess.check_call(
        ["sc", "qc", "SbieSvc"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
      )
      return True
    except subprocess.CalledProcessError:
      return False

  def ensure_installed(self) -> bool:
    if not os.path.exists(self.kmd_util):
      logger.error(f"Sandbox files missing at: {self.kmd_util}")
      return False

    if self.is_service_running():
      logger.debug("Sandbox service is already running.")
      return True

    logger.info("Sandbox service not active. Starting initialization...")

    logger.info("Registering Driver...")
    drv_args = [
      self.kmd_util,
      "install",
      "SbieDrv",
      self.drv_path,
      "type=kernel",
      "start=demand",
      f"msgfile={self.msg_path}",
      "altitude=86900",
    ]
    if not self._run_command(drv_args, "Driver Install"):
      pass

    logger.info("Registering Service...")
    svc_args = [
      self.kmd_util,
      "install",
      "SbieSvc",
      self.svc_path,
      "type=own",
      "start=auto",
      f"msgfile={self.msg_path}",
      "display=Sandboxie Service",
      "group=UIGroup",
    ]
    if not self._run_command(svc_args, "Service Install"):
      pass

    logger.info("Starting Service...")
    start_args = [self.kmd_util, "start", "SbieSvc"]

    if self._run_command(start_args, "Service Start"):
      time.sleep(2)
      if self.is_service_running():
        logger.info("Sandbox is active and ready.")
        return True

    logger.debug("Fallback to 'net start SbieSvc'...")
    subprocess.run(
      ["net", "start", "SbieSvc"],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      creationflags=subprocess.CREATE_NO_WINDOW,
    )

    if self.is_service_running():
      logger.info("Sandbox started via fallback.")
      self._apply_global_settings()
      return True

    logger.error("Failed to start Sandbox service.")
    return False

  def _apply_global_settings(self):
    logger.debug("Applying global silent settings...")

    sbie_ini = os.path.join(self.sb_dir, "SbieIni.exe")

    try:
      subprocess.run(
        [sbie_ini, "set", "GlobalSettings", "HideTrayIcon", "y"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
      )
      subprocess.run(
        [sbie_ini, "set", "GlobalSettings", "PinToTray", "n"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
      )
    except Exception as e:
      logger.debug(f"failed to hide tray icon: {e}")

  def _run_command(self, args: list, label: str) -> bool:
    try:
      result = subprocess.run(
        args,
        cwd=self.sb_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
      )

      if result.returncode == 0:
        logger.debug(f"{label}: Success")
        return True
      else:
        logger.warning(
          f"{label} code {result.returncode}: {result.stdout} {result.stderr}"
        )
        return False

    except Exception as e:
      logger.error(f"{label} failed with exception: {e}")
      return False

  def get_start_exe_path(self):
    return self.start_exe
