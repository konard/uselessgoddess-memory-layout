import ctypes
import os
import subprocess

from constants import PROJECT_ROOT
from core.logging import get_logger

logger = get_logger("terminator")

dll_name = "pyautogui.dll"


def close_cs2_mutex() -> bool:
  dll_path = os.path.join(PROJECT_ROOT, "data", dll_name)
  exe_path = os.path.join(PROJECT_ROOT, "pyautogui.exe")

  if not os.path.exists(dll_path):
    logger.warn(f"pyautogui dll not found: {dll_name}")
    return False

  try:
    lib = ctypes.CDLL(dll_path)

    CloseAllMutexes = lib.CloseAllMutexes
    CloseAllMutexes.argtypes = []
    CloseAllMutexes.restype = ctypes.c_ulong

    logger.debug("calling CloseAllMutexes...")
    result = CloseAllMutexes()

    if result:
      logger.debug("mutexes are closed.")
      return True
    else:
      logger.debug("unable to close throught DLL, trying exe...")
      if os.path.exists(exe_path):
        logger.debug(f"run pyautogui.exe: {exe_path}")
        subprocess.run([exe_path], check=False)
        return True
      else:
        logger.warn(f"pyautogui.exe not found: {exe_path}")

  except OSError as e:
    logger.warn(f"DLL loading error: {e}")

  return False


if __name__ == "__main__":
  if not ctypes.windll.shell32.IsUserAnAdmin():
    print("[-] Run this by admin!")
  else:
    close_cs2_mutex()
