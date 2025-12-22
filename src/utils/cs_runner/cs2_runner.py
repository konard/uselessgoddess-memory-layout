import argparse
import os
import subprocess
import sys
import time
from typing import Optional, List, Set
import json
from pathlib import Path
from typing import Any

_job_handle = None


if os.name == "nt":
  import ctypes
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

  def _setup_kill_on_job_close() -> Optional[int]:
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

  def _assign_process_to_job(proc_handle: int) -> None:
    try:
      global _job_handle
      if _job_handle:
        AssignProcessToJobObject(
          wintypes.HANDLE(_job_handle), wintypes.HANDLE(proc_handle)
        )
    except Exception:
      pass


def get_pids_by_name(process_name: str) -> Set[int]:
  pids = set()
  try:
    cmd = [
      "tasklist",
      "/FI",
      f"IMAGENAME eq {process_name}",
      "/FO",
      "CSV",
      "/NH",
    ]
    result = subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      encoding="oem",
      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    for line in result.stdout.splitlines():
      line = line.strip()
      if not line:
        continue
      parts = line.split('","')
      if len(parts) > 1:
        try:
          pid_str = parts[1].replace('"', "")
          pids.add(int(pid_str))
        except ValueError:
          pass
  except Exception as e:
    print(f"Error getting PIDs for {process_name}: {e}")
  return pids


def is_process_running(pid: int) -> bool:
  try:
    cmd = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
    result = subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      encoding="oem",
      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return str(pid) in result.stdout
  except Exception:
    return False


def build_cs2_launch_args(
  steam_path: str,
  appid: str = "730",
  win_w: int = 360,
  win_h: int = 270,
  sandboxie_path: str = None,
  box_name: str = None,
) -> list[str]:
  steam_args = [
    steam_path,
    "-nofriendsui",
    "-vgui",
    "-noreactlogin",
    "-noverifyfiles",
    "-nobootstrapupdate",
    "-skipinitialbootstrap",
    "-norepairfiles",
    "-overridepackageurl",
    "-disable-winh264",
    "-applaunch",
    appid,
    "+exec",
    "yacs.cfg",
    "+fps_max",
    "30",
    "-window",
    "-w",
    str(win_w),
    "-h",
    str(win_h),
    "-language",
    "russian",
    "-swapcores",
    "-noqueuedload",
    "-vrdisable",
    "-nopreload",
    "-limitvsconst",
    "-softparticlesdefaultoff",
    "-nohltv",
    "-nosound",
    "-novid",
    "+violence_hblood",
    "0",
    "+sethdmodels",
    "0",
    "+mat_disable_fancy_blending",
    "1",
    "+r_dynamic",
    "0",
  ]

  if sandboxie_path and box_name:
    cmd = [
      sandboxie_path,
      f"/box:{box_name}",
      "/silent",
      steam_args[0],
    ]
    cmd.extend(steam_args[1:])
    return cmd

  return steam_args


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


def get_child_processes_wmic(parent_pid: int) -> List[tuple]:
  processes = []
  try:
    cmd = [
      "wmic",
      "process",
      "get",
      "ProcessId,Name,ParentProcessId",
      "/format:csv",
    ]
    result = subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      encoding="oem",
      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    lines = result.stdout.strip().splitlines()
    if not lines:
      return []

    header_idx = -1
    for i, line in enumerate(lines):
      if "ProcessId" in line and "Name" in line:
        header_idx = i
        break

    if header_idx == -1:
      return []

    header = lines[header_idx].split(",")
    pid_idx = -1
    name_idx = -1
    ppid_idx = -1

    for i, col in enumerate(header):
      col = col.strip()
      if col == "ProcessId":
        pid_idx = i
      elif col == "Name":
        name_idx = i
      elif col == "ParentProcessId":
        ppid_idx = i

    if pid_idx == -1 or name_idx == -1 or ppid_idx == -1:
      return []

    for line in lines[header_idx + 1 :]:
      parts = line.split(",")
      if len(parts) <= max(pid_idx, name_idx, ppid_idx):
        continue
      try:
        pid = int(parts[pid_idx])
        name = parts[name_idx]
        ppid = int(parts[ppid_idx])
        processes.append((pid, name, ppid))
      except ValueError:
        continue
  except Exception as e:
    print(f"Error getting processes: {e}")
  return processes


def find_child_processes_recursive(
  parent_pid: int, all_processes: List[tuple]
) -> List[tuple]:
  """
  Рекурсивно находит всех дочерних процессов

  Args:
    parent_pid: PID родительского процесса
    all_processes: Список всех процессов (pid, name, parent_pid)

  Returns:
    Список дочерних процессов
  """
  children = []

  # Находим прямых детей
  direct_children = [p for p in all_processes if p[2] == parent_pid]
  children.extend(direct_children)

  # Рекурсивно находим детей детей
  for child in direct_children:
    grandchildren = find_child_processes_recursive(child[0], all_processes)
    children.extend(grandchildren)

  return children


def wait_for_child_processes(
  parent_pid: int, target_names: List[str] = None, timeout: int = 60
) -> List[int]:
  """
  Ждет появления дочерних процессов у родительского процесса

  Args:
    parent_pid: PID родительского процесса
    target_names: Список имен процессов для поиска (например, ['cs2.exe'])
    timeout: Максимальное время ожидания в секундах

  Returns:
    Список PID найденных дочерних процессов
  """
  if target_names is None:
    target_names = ["cs2.exe", "csgo.exe"]

  start_time = time.time()
  found_pids = []

  print(f"Ожидаем дочерние процессы для PID {parent_pid}...")
  print(f"Ищем процессы: {target_names}")

  while time.time() - start_time < timeout:
    try:
      # Получаем все процессы
      all_processes = get_child_processes_wmic(parent_pid)
      if not all_processes:
        time.sleep(2)
        continue

      # Находим дочерние процессы
      children = find_child_processes_recursive(parent_pid, all_processes)

      for pid, name, ppid in children:
        name_lower = name.lower()
        if any(target.lower() in name_lower for target in target_names):
          if pid not in found_pids:
            found_pids.append(pid)
            print(f"Найден дочерний процесс: {name} (PID: {pid})")

      if found_pids:
        print(f"Найдено {len(found_pids)} дочерних процессов: {found_pids}")
        return found_pids

      if children:
        child_names = [f"{name}({pid})" for pid, name, ppid in children]
        if child_names:
          # print(f"Текущие дочерние процессы: {', '.join(child_names)}")
          pass

    except Exception as e:
      print(f"Ошибка при получении процессов: {e}")

    time.sleep(2)

  print(f"Тайм-аут ожидания дочерних процессов ({timeout}с)")
  return found_pids


def wait_for_window_visibility(pids: List[int], timeout: int = 60) -> bool:
  if os.name != "nt":
    return True

  print(f"Waiting for window visibility for PIDs: {pids}...")
  start_time = time.time()

  try:
    import ctypes

    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(
      ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    while time.time() - start_time < timeout:
      visible = False

      def enum_cb(hwnd, _):
        nonlocal visible
        if user32.IsWindowVisible(hwnd):
          pid = ctypes.c_ulong()
          user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
          if pid.value in pids:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
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
    # Fallback to simple sleep if something breaks
    return False

  print("Timeout waiting for window.")
  return False


def main() -> int:
  # hide_console_window()
  print("Runner initialized.")

  parser = argparse.ArgumentParser()
  parser.add_argument("--steamPath", required=True)
  parser.add_argument("--quiet", action="store_true")
  parser.add_argument("--login", type=str)
  parser.add_argument("--w", type=int, default=360)
  parser.add_argument("--h", type=int, default=270)
  parser.add_argument("--hook_dll", required=True)
  parser.add_argument("--sandboxiePath", type=str, help="Path to Start.exe")
  parser.add_argument("--box", type=str, help="Sandbox Name")

  args = parser.parse_args()

  console_title = f"Runner-{args.login or 'Unknown'}"
  set_console_title(console_title)

  if os.name == "nt" and not args.box:
    global _job_handle
    _job_handle = _setup_kill_on_job_close()

  baseline_steam_pids = get_pids_by_name("steam.exe")
  print(f"Baseline Steam PIDs: {baseline_steam_pids}")

  opts = build_cs2_launch_args(
    args.steamPath,
    win_w=args.w,
    win_h=args.h,
    sandboxie_path=args.sandboxiePath,
    box_name=args.box,
  )

  proc = subprocess.Popen(
    opts,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    encoding="utf-8",
    errors="replace",
    cwd=os.getcwd(),
    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
  )

  print("Launch command executed.")

  target_steam_pid = None

  search_timeout = 180
  start_search = time.time()

  print("Waiting for new steam.exe process...")

  while time.time() - start_search < search_timeout:
    current_pids = get_pids_by_name("steam.exe")
    new_pids = current_pids - baseline_steam_pids

    if new_pids:
      target_steam_pid = list(new_pids)[0]
      print(f"Detected new Steam PID: {target_steam_pid}")
      break

    if not args.box and proc.poll() is not None:
      print("Native process exited prematurely.")
      return 0

    time.sleep(2)

  if target_steam_pid:
    # Wait for CS2 process and window
    print("Waiting for CS2 process...")
    cs2_pids = wait_for_child_processes(target_steam_pid, ["cs2.exe"])

    if cs2_pids:
      if wait_for_window_visibility(cs2_pids, timeout=120):
        print("CS2 window detected. Proceeding to inject.")
        time.sleep(2)  # Small buffer
      else:
        print("CS2 window not detected. Proceeding anyway...")
    else:
      print("CS2 process not found. Proceeding with default delay...")
      time.sleep(10)

    syswow64 = os.path.join(
      os.environ.get("SystemRoot", "C:\\Windows"), "SysWOW64"
    )
    rundll32_path = os.path.join(syswow64, "rundll32.exe")

    if not os.path.exists(rundll32_path):
      rundll32_path = "rundll32.exe"

    hook_cmd = []
    if args.box and args.sandboxiePath:
      print(f"Injecting into Steam PID {target_steam_pid} (Inside Box)...")
      hook_cmd = [
        args.sandboxiePath,
        f"/box:{args.box}",
        "/silent",
        rundll32_path,
        f"{args.hook_dll},Inject",
        str(target_steam_pid),
        str(args.login),
      ]
    else:
      print(f"Injecting into Steam PID {target_steam_pid} (Native)...")
      hook_cmd = [
        rundll32_path,
        f"{args.hook_dll},Inject",
        str(target_steam_pid),
        str(args.login),
      ]

    try:
      injector = subprocess.run(
        hook_cmd,
        capture_output=True,
        text=True,
      )
      print(f"Injector output: {injector.stdout}")
      if injector.stderr:
        print(f"Injector stderr: {injector.stderr}")

      if injector.returncode == 0:
        print("Inject command sent.")
      else:
        print(f"Inject failed: {injector.stderr}")
    except Exception as e:
      print(f"Inject exception: {e}")

  else:
    print("Timeout: New Steam process not found.")

  print("Monitoring target Steam process...")

  if target_steam_pid:
    try:
      while is_process_running(target_steam_pid):
        time.sleep(5)
      print("Target Steam process terminated. Exiting.")
    except KeyboardInterrupt:
      pass
  else:
    print("No target process to monitor. Exiting.")

  return 0


if __name__ == "__main__":
  try:
    sys.exit(main())
  except KeyboardInterrupt:
    pass
  except Exception as e:
    import traceback

    traceback.print_exc()
    print(f"Critical error: {e}")
    input("Press Enter to exit...")
