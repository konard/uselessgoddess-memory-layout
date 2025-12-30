import psutil
import win32gui
import win32process


def find_window_by_name(window_name):
  hwnd = win32gui.FindWindow(None, window_name)
  if hwnd:
    return hwnd

  def callback(hwnd, extra):
    if win32gui.IsWindowVisible(hwnd):
      title = win32gui.GetWindowText(hwnd)
      if title and window_name.lower() in title.lower():
        extra.append((hwnd, title))

  windows = []
  win32gui.EnumWindows(callback, windows)

  if windows:
    return windows[0][0]
  return None


def get_parent_processes(pid):
  chain = []
  try:
    process = psutil.Process(pid)
    chain.append(
      (pid, process.name(), process.exe() if hasattr(process, "exe") else "N/A")
    )

    while True:
      try:
        parent = process.parent()
        if parent is None:
          break
        chain.append(
          (
            parent.pid,
            parent.name(),
            parent.exe() if hasattr(parent, "exe") else "N/A",
          )
        )
        process = parent
      except (psutil.NoSuchProcess, psutil.AccessDenied):
        break
  except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
    print(f"Ошибка при получении процесса {pid}: {e}")

  return chain


def get_steam_pid(window_name):
  hwnd = find_window_by_name(window_name)
  if not hwnd:
    return None

  _, pid = win32process.GetWindowThreadProcessId(hwnd)

  chain = get_parent_processes(pid)

  steam_process = None
  for proc_pid, proc_name, proc_path in chain:
    if proc_name.lower() == "steam.exe":
      steam_process = (proc_pid, proc_name, proc_path)
      break

  if steam_process:
    proc_pid, proc_name, proc_path = steam_process
    return proc_pid
  return None
