import contextlib
import os
import sys
from typing import Optional

_job_handle = None

if os.name == "nt":
  import ctypes
  import winreg
  from ctypes import wintypes

  # Constants
  JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
  JobObjectExtendedLimitInformation = 9

  class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
      ("ReadOperationCount", wintypes.ULARGE_INTEGER),
      ("WriteOperationCount", wintypes.ULARGE_INTEGER),
      ("OtherOperationCount", wintypes.ULARGE_INTEGER),
      ("ReadTransferCount", wintypes.ULARGE_INTEGER),
      ("WriteTransferCount", wintypes.ULARGE_INTEGER),
      ("OtherTransferCount", wintypes.ULARGE_INTEGER),
    ]

  class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
      ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
      ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
      ("LimitFlags", wintypes.DWORD),
      ("MinimumWorkingSetSize", ctypes.c_void_p),
      ("MaximumWorkingSetSize", ctypes.c_void_p),
      ("ActiveProcessLimit", wintypes.DWORD),
      ("Affinity", ctypes.c_void_p),
      ("PriorityClass", wintypes.DWORD),
      ("SchedulingClass", wintypes.DWORD),
    ]

  class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
      ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
      ("IoInfo", IO_COUNTERS),
      ("ProcessMemoryLimit", ctypes.c_void_p),
      ("JobMemoryLimit", ctypes.c_void_p),
      ("PeakProcessMemoryUsed", ctypes.c_void_p),
      ("PeakJobMemoryUsed", ctypes.c_void_p),
    ]

  kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
  CreateJobObjectW = kernel32.CreateJobObjectW
  CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
  CreateJobObjectW.restype = wintypes.HANDLE

  SetInformationJobObject = kernel32.SetInformationJobObject
  SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    wintypes.INT,
    ctypes.c_void_p,
    wintypes.DWORD,
  ]
  SetInformationJobObject.restype = wintypes.BOOL

  AssignProcessToJobObject = kernel32.AssignProcessToJobObject
  AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
  AssignProcessToJobObject.restype = wintypes.BOOL

  GetCurrentProcess = kernel32.GetCurrentProcess
  GetCurrentProcess.argtypes = []
  GetCurrentProcess.restype = wintypes.HANDLE


def set_autologin_user(username):
  """Меняет пользователя в реестре перед запуском."""
  if os.name != "nt":
    return
  try:
    import winreg

    key_path = r"Software\Valve\Steam"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
      winreg.SetValueEx(key, "AutoLoginUser", 0, winreg.REG_SZ, username)
      winreg.SetValueEx(key, "RememberPassword", 0, winreg.REG_DWORD, 1)
      # Иногда помогает сброс PID старого процесса в реестре
      with contextlib.suppress(Exception):
        winreg.DeleteValue(key, "ActiveProcess")
    print(f"[*] Реестр: AutoLoginUser установлен на {username}")
  except Exception as e:
    print(f"[!] Ошибка записи в реестр: {e}")


def setup_kill_on_job_close() -> int | None:
  if os.name != "nt":
    return None
  try:
    hJob = CreateJobObjectW(None, None)
    if not hJob:
      return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = SetInformationJobObject(
      hJob,
      JobObjectExtendedLimitInformation,
      ctypes.byref(info),
      ctypes.sizeof(info),
    )
    if not ok:
      return None
    if not AssignProcessToJobObject(hJob, GetCurrentProcess()):
      return None
    return int(hJob)
  except Exception:
    return None


def assign_process_to_job(job_handle: int, proc_handle: int) -> None:
  if os.name != "nt":
    return
  with contextlib.suppress(Exception):
    AssignProcessToJobObject(wintypes.HANDLE(job_handle), wintypes.HANDLE(proc_handle))


def set_console_title(title: str) -> None:
  if os.name == "nt":
    try:
      import ctypes

      ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
      pass


def hide_console_window() -> None:
  if os.name == "nt":
    try:
      import ctypes

      hwnd = ctypes.windll.kernel32.GetConsoleWindow()
      if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
      pass
