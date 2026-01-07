import ctypes
from ctypes import wintypes

import psutil

from core.logging import get_logger

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = 0x1F0FFF

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

SetProcessWorkingSetSize = kernel32.SetProcessWorkingSetSize
SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t]
SetProcessWorkingSetSize.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

logger = get_logger("mem_reduct")


def trim_memory(pid, process_name):
  try:
    handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
      return

    success = SetProcessWorkingSetSize(handle, -1, -1)

    if success:
      print(f"[OK] cleaned PID {pid}: {process_name}")
    else:
      print(f"[FAIL] failed to clean PID {pid}")

    CloseHandle(handle)
  except Exception as e:
    print(f"error with PID {pid}: {e}")


def clean_memory():
  target_process = "cs2.exe"
  logger.trace(f"STARTED AUTO-CLEANER for {target_process}")

  for proc in psutil.process_iter(["pid", "name"]):
    try:
      if proc.info["name"] and proc.info["name"].lower() == target_process:
        trim_memory(proc.info["pid"], proc.info["name"])
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
      pass
