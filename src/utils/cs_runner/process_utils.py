import subprocess
import os
import time
import ctypes
from ctypes import wintypes
from typing import Set, List, Tuple, Optional

# --- WinAPI CONSTANTS & STRUCTURES ---
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32(ctypes.Structure):
  _fields_ = [
    ("dwSize", wintypes.DWORD),
    ("cntUsage", wintypes.DWORD),
    ("th32ProcessID", wintypes.DWORD),
    ("th32DefaultHeapID", ctypes.c_void_p),
    ("th32ModuleID", wintypes.DWORD),
    ("cntThreads", wintypes.DWORD),
    ("th32ParentProcessID", wintypes.DWORD),
    ("pcPriClassBase", wintypes.LONG),
    ("dwFlags", wintypes.DWORD),
    ("szExeFile", ctypes.c_wchar * 260),
  ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
CreateToolhelp32Snapshot.restype = wintypes.HANDLE

Process32First = kernel32.Process32FirstW
Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
Process32First.restype = wintypes.BOOL

Process32Next = kernel32.Process32NextW
Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
Process32Next.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def get_processes_fast() -> List[Tuple[int, str, int]]:
  """
  Получает список процессов (PID, Name, ParentPID) через WinAPI (быстро и без wmic).
  """
  processes = []
  h_snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)

  if h_snap == wintypes.HANDLE(-1).value:
    return []

  pe32 = PROCESSENTRY32()
  pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

  if Process32First(h_snap, ctypes.byref(pe32)):
    while True:
      processes.append(
        (pe32.th32ProcessID, pe32.szExeFile, pe32.th32ParentProcessID)
      )
      if not Process32Next(h_snap, ctypes.byref(pe32)):
        break

  CloseHandle(h_snap)
  return processes


def get_process_parent_pid(pid: int) -> Optional[int]:
  """
  Возвращает Parent PID для указанного PID.
  """
  processes = get_processes_fast()
  for p_pid, p_name, p_parent in processes:
    if p_pid == pid:
      return p_parent
  return None


def get_pids_by_name(process_name: str) -> Set[int]:
  pids = set()
  try:
    processes = get_processes_fast()
    for pid, name, ppid in processes:
      if name.lower() == process_name.lower():
        pids.add(pid)
  except Exception as e:
    print(f"Error getting PIDs for {process_name}: {e}")
  return pids


def is_process_running(pid: int) -> bool:
  processes = get_processes_fast()
  for p_pid, _, _ in processes:
    if p_pid == pid:
      return True
  return False


def find_child_processes_recursive(
  parent_pid: int, all_processes: List[Tuple[int, str, int]]
) -> List[Tuple[int, str, int]]:
  children = []
  direct_children = [p for p in all_processes if p[2] == parent_pid]
  children.extend(direct_children)
  for child in direct_children:
    grandchildren = find_child_processes_recursive(child[0], all_processes)
    children.extend(grandchildren)
  return children


def wait_for_child_processes(
  parent_pid: int, target_names: List[str] = None, timeout: int = 60
) -> List[int]:
  if target_names is None:
    target_names = ["cs2.exe", "csgo.exe"]

  start_time = time.time()
  found_pids = []

  print(f"Ожидаем дочерние процессы для PID {parent_pid}...")

  while time.time() - start_time < timeout:
    try:
      all_processes = get_processes_fast()
      if not all_processes:
        time.sleep(1)
        continue

      children = find_child_processes_recursive(parent_pid, all_processes)

      for pid, name, ppid in children:
        name_lower = name.lower()
        if any(target.lower() in name_lower for target in target_names):
          if pid not in found_pids:
            found_pids.append(pid)
            print(f"Найден дочерний процесс: {name} (PID: {pid})")

      if found_pids:
        return found_pids

    except Exception as e:
      print(f"Ошибка при поиске процессов: {e}")

    time.sleep(1.5)

  print(f"Тайм-аут ожидания дочерних процессов ({timeout}с)")
  return found_pids


def wait_for_window_visibility(pids: List[int], timeout: int = 60) -> bool:
  if os.name != "nt":
    return True

  print(f"Waiting for window visibility for PIDs: {pids}...")
  start_time = time.time()

  try:
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(
      ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    while time.time() - start_time < timeout:
      visible = False

      def enum_cb(hwnd, _):
        nonlocal visible
        if user32.IsWindowVisible(hwnd):
          pid = wintypes.DWORD()
          user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
          if pid.value in pids:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0:
              visible = True
              return False
        return True

      user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

      if visible:
        print("Window detected.")
        return True

      time.sleep(1)
  except Exception as e:
    print(f"Error waiting for window: {e}")
    return False

  print("Timeout waiting for window.")
  return False
