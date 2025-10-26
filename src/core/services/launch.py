import os
import time
import subprocess
import pyautogui
from src.core.account import Account, RunningAccount
from src.core.logging import get_logger
from src.core.services import WindowService

logger = get_logger("sv.launch")


def build_runner_launch_args(steam_login: str):
  # settings = load_settings()
  # win_w = settings.get("win_w", 360)
  # win_h = settings.get("win_h", 270)

  win_w = 360
  win_h = 270

  args = [
    # f'cmd /c "title Runner-{steam_login}";',
    "matchid_sender.exe",
    "--cs2path",
    settings.get("csgo_path"),
    "--steamPath",
    settings.get("steam_path"),
    "--host",
    settings.get("host", "127.0.0.1"),
    "--port",
    settings.get("port", "9009"),
    "--w",
    str(win_w),
    "--h",
    str(win_h),
    "--login",
    steam_login,
  ]

  logger.debug(f"runner args: {args}")

  return args


def detect_state_by_screenshot(
  screenshot: str, confidence: float = 0.8
) -> bool:
  try:
    return (
      pyautogui.locateOnScreen(screenshot, confidence=confidence) is not None
    )
  except Exception as e:
    logger.debug(f"error wh screenshot detection: {e}")
    return False


def steam_login(
  login: str,
  password: str,
  shared_secret: str,
  kill_existing: bool = False,
) -> int:
  if kill_existing:
    os.system("taskkill /f /im steam.exe >nul 2>&1")
    time.sleep(1)

  # Launch Steam runner as independent process with custom window title
  subprocess.Popen(
    build_runner_launch_args(steam_login=login),
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    | subprocess.DETACHED_PROCESS,
    close_fds=True,
  )
  autoit.auto_it_set_option("WinTitleMatchMode", 2)
  while not autoit.win_exists("Войти в Steam"):
    logger.debug(f"[{login}] Waiting for Steam window")
    time.sleep(1)
  time.sleep(1)
  logger.debug(f"[{login}] Steam launched")
  # Type credentials
  pyautogui.typewrite(login)
  logger.debug(f"[{login}] Login typed")
  pyautogui.press("tab")
  logger.debug(f"[{login}] Tab pressed")
  pyautogui.typewrite(password)
  logger.debug(f"[{login}] Password typed")
  pyautogui.press("enter")
  logger.debug(f"[{login}] Enter pressed")

  while detect_state_by_screenshot("resources/img/log-ru.jpg"):
    logger.debug(f"[{login}] Waiting for Guard window")
    time.sleep(1)

  logger.debug(f"[{login}] Credentials typed")
  # Type guard code
  code = TwoFactorService.generate_2fa_code(shared_secret)
  pyautogui.typewrite(code)
  pyautogui.press("enter")
  logger.debug(f"[{login}] Guard code typed")


class LaunchService:
  @staticmethod
  def launch_account(
    account: Account, running_accounts: list[RunningAccount]
  ) -> bool:
    login = account.login
    try:
      logger.info(f"launching steam +{login}")

      steam_login(
        login=login,
        password=account.password,
        shared_secret=account.shared_secret,
        kill_existing=False,
      )

      logger.info(f"[{login}] Waiting for 'Counter-Strike 2' window...")
      if not WindowService.wait_for_window("Counter-Strike 2", timeout_sec=60):
        raise Exception("CS2 window did not appear in time.")

      logger.info(f"[{login}] 'Counter-Strike 2' window found. Renaming...")
      new_title = f"[{login}] # CS"
      if not WindowService.rename_window("Counter-Strike 2", new_title):
        raise Exception("Failed to rename CS2 window.")

      logger.info(f"[{login}] Moving window to its position...")
      pos_x, pos_y = WindowService.get_next_window_position(running_accounts)
      WindowService.move_window_to_position(new_title, pos_x, pos_y)

      logger.info(f"Account {login} launched and configured successfully!")
      return True

    except Exception as e:
      logger.error(f"[{login}] Failed to launch account: {e}")
      return False
