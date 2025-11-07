import argparse
import os
import subprocess
import sys
import time
from typing import Optional, List
import json
from pathlib import Path
from typing import Any

_job_handle = None


def load_settings(file_path: str = "settings.json") -> dict[str, Any]:
  with open(Path(file_path), encoding="utf-8") as f:
    return json.load(f)


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
    """Create a Job object with KILL_ON_JOB_CLOSE and assign current process.
    Returns job handle (int) or None on failure.
    """
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

      # Assign current process; children will join the same job by default
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


def build_cs2_launch_args(
  steam_path: str,
  appid: str = "730",
  win_w: int = 360,
  win_h: int = 270,
  steam: List[str] = None,
  cs2: List[str] = None,
) -> list[str]:
  args = [
    steam_path,
  ]
  if steam:
    args.extend(steam)

  args.extend(
    [
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
    ]
  )
  if cs2:
    args.extend(cs2)

  return args


def get_child_processes_wmic(parent_pid: int) -> List[tuple]:
  """
  Получает дочерние процессы через wmic (Windows Management Instrumentation)

  Returns:
    Список кортежей (pid, name, parent_pid)
  """
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
      encoding='utf-8',
      errors='replace',
      creationflags=subprocess.CREATE_NO_WINDOW,
    )

    if result.returncode != 0:
      return []

    processes = []
    lines = result.stdout.strip().split("\n")

    for line in lines[1:]:  # Пропускаем заголовок
      if not line.strip():
        continue

      parts = line.split(",")
      if len(parts) >= 4:
        try:
          # Формат: Node,Name,ParentProcessId,ProcessId
          name = parts[1].strip()
          parent_pid_str = parts[2].strip()
          pid_str = parts[3].strip()

          if name and parent_pid_str and pid_str:
            processes.append((int(pid_str), name, int(parent_pid_str)))
        except (ValueError, IndexError):
          continue

    return processes
  except Exception:
    return []


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
          print(f"Текущие дочерние процессы: {', '.join(child_names)}")

    except Exception as e:
      print(f"Ошибка при получении процессов: {e}")

    time.sleep(2)

  print(f"Тайм-аут ожидания дочерних процессов ({timeout}с)")
  return found_pids


def is_process_running(pid: int) -> bool:
  """Проверяет, запущен ли процесс с данным PID"""
  try:
    cmd = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"]
    result = subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      encoding='utf-8',
      errors='replace',
      creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return str(pid) in result.stdout
  except Exception:
    return False


# python matchid_sender.py --cs2path "P:\steam\steamapps\common\Counter-Strike Global Offensive" --steamPath "P:\js\steam_bollerplate\steam.exe" --host 127.0.0.1 --port 9009 --quiet --w 360 --h 270
def set_console_title(title: str) -> None:
  """Set console window title"""
  if os.name == "nt":
    try:
      import ctypes

      ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
      pass


def main() -> int:
  print(f"runner started")

  parser = argparse.ArgumentParser(
    description=(
      "Читает console.log CS2 и отправляет последнее вхождение 'match_id=*' "
      "по TCP на localhost:9009 при появлении/изменении."
    )
  )
  parser.add_argument(
    "--steamPath",
    required=True,
    help="Путь до Steam (необязателен для логики, но принимается)",
  )
  parser.add_argument(
    "--quiet", action="store_true", help="Тише (минимум логов)"
  )
  parser.add_argument("--login", type=str, help="Логин Steam")
  parser.add_argument("--w", type=int, default=360)
  parser.add_argument("--h", type=int, default=270)
  args = parser.parse_args()

  if not args.quiet:
    print(args)

  console_title = f"Runner-{args.login or 'Unknown'}"
  set_console_title(console_title)

  if os.name == "nt":
    global _job_handle
    _job_handle = _setup_kill_on_job_close()

  opts = build_cs2_launch_args(args.steamPath, win_w=args.w, win_h=args.h)
  if not args.quiet:
    print(opts)

  proc = subprocess.Popen(
    opts,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    encoding='utf-8',
    errors='replace',
  )
  print(f"Steam процесс запущен с PID: {proc.pid}")

  if os.name == "nt":
    try:
      proc_handle = getattr(proc, "_handle", None)
      if proc_handle:
        _assign_process_to_job(int(proc_handle))
    except Exception:
      pass

  cs2_pids = wait_for_child_processes(
    proc.pid, ["steamwebhelper.exe"], timeout=120
  )

  if cs2_pids:
    print(f"steamwebhelper найдены: {cs2_pids}")

    hook = subprocess.Popen(
      ["rundll32", "NetHook2.dll,Inject", str(proc.pid), str(args.login)],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      encoding='utf-8',
      errors='replace',
    )
    print(f"Hook запущен с PID: {hook.pid}")
  else:
    print("CS2 процессы не найдены в течение тайм-аута")

  try:
    while True:
      time.sleep(5)
      # Проверяем, что основной процесс еще жив
      if proc.poll() is not None:
        print("Основной процесс завершился")
        break
  except KeyboardInterrupt:
    print("\nЗавершение работы...")
    try:
      proc.terminate()
    except:
      pass


if __name__ == "__main__":
  try:
    sys.exit(main())
  except KeyboardInterrupt:
    pass
