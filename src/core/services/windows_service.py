import contextlib
import time

import autoit
import pyautogui
import win32api
import win32con
import win32gui
import win32process

from constants import win_h, win_w
from core.account import Account, RunningAccount
from core.logging import get_logger
from core.services.process import ProcessService
from core.utils import async_methods

logger = get_logger("window")


@async_methods
class WindowService:
  """Сервис для управления окнами"""

  @staticmethod
  def update_window_position(account_data, pos_x: int, pos_y: int) -> None:
    """Обновить позицию окна в данных аккаунта"""
    account_data.posX = pos_x
    account_data.posY = pos_y

  @staticmethod
  def enum_windows():
    windows = []

    def callback(hwnd, extra):
      if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title:
          windows.append((hwnd, title))

    win32gui.EnumWindows(callback, None)
    return windows

  @staticmethod
  def focus_window(window_title: str):
    """Фокусирует окно CS2 по заголовку"""
    try:
      hwnd = win32gui.FindWindow(None, window_title)
      if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        logger.debug(f"Окно сфокусировано: {window_title} (hwnd={hwnd})")
        return hwnd
      else:
        logger.debug(f"Окно '{window_title}' не найдено")
        return None
    except Exception as e:
      print(f"Ошибка при фокусировке окна: {e}")
      return None

  @staticmethod
  def get_window_info(window_title: str) -> dict | None:
    """Получить информацию об окне: позицию (posX, posY) и PID"""
    try:
      hwnd = win32gui.FindWindow(None, window_title)
      if not hwnd:
        for h, title in WindowService.enum_windows():
          if title and (window_title in title):
            hwnd = h
            break

      if not hwnd:
        return None

      rect = win32gui.GetWindowRect(hwnd)
      pos_x = rect[0]
      pos_y = rect[1]

      _, pid = win32process.GetWindowThreadProcessId(hwnd)

      return {"posX": pos_x, "posY": pos_y, "pid": pid, "hwnd": hwnd}

    except Exception as e:
      logger.error(f"Ошибка при получении информации об окне '{window_title}': {e}")
      return None

  @staticmethod
  def window_exists(window_title: str) -> bool:
    """Проверить существование окна с указанным заголовком"""
    try:
      hwnd = win32gui.FindWindow(None, window_title)
      return hwnd != 0
    except Exception as e:
      logger.error(f"Ошибка при проверке существования окна '{window_title}': {e}")
      return False

  @staticmethod
  def find_window_by_partial_title(partial_title: str) -> str | None:
    """Найти окно по частичному совпадению заголовка"""
    try:
      for _, title in WindowService.enum_windows():
        if partial_title in title:
          return title
    except Exception as e:
      logger.error(
        f"Ошибка при поиске окна по частичному заголовку '{partial_title}': {e}"
      )
    return None

  @staticmethod
  def rename_window(window_title: str, new_title: str) -> str | None:
    try:
      for _, title in WindowService.enum_windows():
        if title and (window_title in title):
          try:
            autoit.win_activate(title)
            autoit.win_wait_active(title)
            autoit.win_set_title(title, new_title)
            return new_title
          except Exception:
            return title
    except Exception:
      return None
    return None

  @staticmethod
  def move_window_to_position(title: str, pos_x: int, pos_y: int):
    logger.trace(f"move window={title} to x={pos_x} y={pos_y}")

    with contextlib.suppress(Exception):
      autoit.auto_it_set_option("WinTitleMatchMode", 2)

    try:
      if autoit.win_exists(title):
        autoit.win_activate(title)
        autoit.win_wait_active(title, timeout=5)
        autoit.win_move(title, pos_x, pos_y)
        return True
    except Exception as e:
      logger.error(f"Failed to move window '{title}': {e}")

  @staticmethod
  def get_next_window_position(
    accounts: list[Account],
  ) -> tuple[int, int]:
    window_width, window_height = win_w, win_h
    screen_width = pyautogui.size()[0]

    running_accounts: list[RunningAccount] = WindowService.scan_cs2_windows(accounts)

    max_cols = max(1, screen_width // window_width)
    occupied = set()
    logger.debug(f"Running accounts: {running_accounts}")
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
  def wait_for_window(window_title: str, timeout_sec: int = 120) -> bool:
    import time

    try:
      start = time.time()
      last_log = time.time()

      autoit.auto_it_set_option("WinTitleMatchMode", 2)

      while True:
        try:
          if autoit.win_exists(window_title):
            return True
        except Exception:
          pass

        if time.time() - last_log >= 5:
          logger.debug(f"Waiting window... target title -> {window_title}")
          last_log = time.time()

        if time.time() - start > timeout_sec:
          return False

        time.sleep(1)
    except Exception as e:
      print(f"Error waiting for window: {window_title}, error: {e}")
    return False

  @staticmethod
  def scan_cs2_windows(
    accounts: list[Account], values=True
  ) -> list[RunningAccount] | list[str]:
    running = {}

    if isinstance(accounts, dict):
      accounts_list = list(accounts.values())
    else:
      accounts_list = accounts
    accounts_dict = {acc.login: acc for acc in accounts_list}

    def callback(hwnd, lParam):
      if not win32gui.IsWindowVisible(hwnd):
        return

      title = win32gui.GetWindowText(hwnd)
      if title.startswith("[") and "] # CS" in title:
        try:
          login = title.split("]")[0][1:]
          rect = win32gui.GetWindowRect(hwnd)
          window_info = WindowService.get_window_info(
            RunningAccount.generate_window_title(login)
          )
          if accounts_dict.get(login) is not None:
            acc = accounts_dict[login]
            running[login] = RunningAccount(
              login=login,
              password=acc.password,
              shared_secret=acc.shared_secret,
              identity_secret=acc.identity_secret,
              steam_id=acc.steam_id,
              posX=rect[0],
              posY=rect[1],
              runner_pid=ProcessService.get_runner_pid(window_info.get("pid")),
            )
            running[login].lock = acc.lock
        except Exception as e:
          print(e)

    win32gui.EnumWindows(callback, None)
    if values:
      return list(running.values())
    return list(running.keys())

  @staticmethod
  def arrange_windows(accounts: list[Account], dimension: tuple[int, int]):
    width, height = dimension

    try:
      screen_w = win32api.GetSystemMetrics(0)
      max_cols = max(1, screen_w // width)
      placed_count = 0

      for account in accounts:
        window_title = f"[{account.login}] # CS"

        hwnd = win32gui.FindWindow(None, window_title)

        if hwnd:
          row = placed_count // max_cols
          col = placed_count % max_cols

          x = col * width
          y = row * height

          try:
            win32gui.MoveWindow(hwnd, x, y, width, height, True)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)

            if hasattr(account, "posX"):
              account.posX = x
              account.posY = y

            placed_count += 1
            logger.debug(f"Arranged {account.login} to ({x}, {y})")

          except Exception as e:
            logger.error(f"Failed to move window for {account.login}: {e}")
        else:
          logger.trace(f"Window not found for arranging: {account.login}")

        time.sleep(0.5)
    except Exception as e:
      logger.error(f"Global arrange error: {e}")

  @staticmethod
  async def focus_window_async(window_title: str): ...

  @staticmethod
  async def wait_for_window_async(window_title: str, timeout_sec: int = 120) -> bool: ...
