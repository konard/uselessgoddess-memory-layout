import subprocess
import os
import time
from typing import Set, List


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
        # child_names = [f"{name}({pid})" for pid, name, ppid in children]
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
    return False

  print("Timeout waiting for window.")
  return False
