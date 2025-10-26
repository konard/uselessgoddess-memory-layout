import time
from typing import Tuple, List, Dict
import win32gui
import win32con
import win32process
import autoit

from core.logging import get_logger
from core.account import RunningAccount, Account

logger = get_logger("sv.window")


class WindowService:
  @staticmethod
  def rename_window(title: str, rename: str) -> bool:
    try:
      autoit.win_set_title(f"[TITLE:{title}]", rename)
      return True
    except Exception as e:
      logger.error(f"Failed to rename window '{title}' to '{rename}': {e}")
      return False

  @staticmethod
  def move_window_to_position(title: str, pos_x: int, pos_y: int):
    try:
      autoit.win_move(title, pos_x, pos_y)
    except Exception as e:
      logger.error(f"Failed to move window '{title}': {e}")

  @staticmethod
  def get_next_window_position(
    running_accounts: List[RunningAccount],
  ) -> Tuple[int, int]:
    # TODO: load from settings
    window_width, window_height = 360, 270
    # TODO: real screen size
    screen_width = 1920

    max_cols = max(1, screen_width // window_width)
    occupied = set()
    for account in running_accounts:
      col = max(0, account.posX // window_width)
      row = max(0, account.posY // window_height)
      occupied.add((row, col))

    row = 0
    while True:
      for col in range(max_cols):
        if (row, col) not in occupied:
          return (col * window_width, row * window_height)
      row += 1

  @staticmethod
  def wait_for_window(title: str, timeout_sec: int = 120) -> bool:
    try:
      return autoit.win_wait(f"[TITLE:{title}]", timeout_sec)
    except Exception as e:
      logger.error(f"Error waiting for window '{title}': {e}")
      return False

  @staticmethod
  def scan_cs2_windows(
    accounts: Dict[str, Account],
  ) -> Dict[str, RunningAccount]:
    running = {}

    def callback(hwnd, extra):
      if not win32gui.IsWindowVisible(hwnd):
        return

      title = win32gui.GetWindowText(hwnd)
      if title.startswith("[") and "] # CS" in title:
        try:
          login = title.split("]")[0][1:]
          rect = win32gui.GetWindowRect(hwnd)
          _, pid = win32process.GetWindowThreadProcessId(hwnd)

          if login in accounts:
            acc = accounts[login]
            running[login] = RunningAccount(
              login=login,
              password=acc.password,
              shared_secret=acc.shared_secret,
              steam_id=acc.steam_id,
              posX=rect[0],
              posY=rect[1],
              runner_pid=pid,
            )
        except Exception:
          pass

    win32gui.EnumWindows(callback, None)
    return running
