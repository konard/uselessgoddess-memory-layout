import time
import base64
import subprocess
import autoit
import pyautogui
import struct
import hmac

from src.core.account import Account, RunningAccount
from src.core.logging import get_logger
from src.core.services import WindowService, UserSettings

logger = get_logger("sv.launch")


def build_runner_launch_args(login: str, settings: UserSettings):
  # TODO! store in settings.json
  host = "127.0.0.1"
  port = "9009"

  args = [
    "matchid_sender.exe",
    "--cs2path",
    settings.cs_path,
    "--steamPath",
    settings.steam_path,
    "--host",
    host,
    "--port",
    port,
    "--w",
    str(settings.win_w),
    "--h",
    str(settings.win_h),
    "--login",
    login,
  ]

  logger.debug(f"run runner with args: {args}")

  return args


def detect_state_by_screenshot(
  screenshot: str, confidence: float = 0.8
) -> bool:
  try:
    return bool(pyautogui.locateOnScreen(screenshot, confidence=confidence))
  except Exception as e:
    logger.debug(f"error wh screenshot detection: {e}")
    return False


def generate_2fa_code(shared_secret: str) -> str:
  if not shared_secret:
    raise ValueError("shared_secret is empty")
  key = base64.b64decode(shared_secret, validate=True)

  timestamp = int(time.time())
  time_buffer = struct.pack(">Q", timestamp // 30)
  hmac_hash = hmac.new(key, time_buffer, "sha1").digest()
  offset = hmac_hash[-1] & 0x0F
  code = struct.unpack(">I", hmac_hash[offset : offset + 4])[0] & 0x7FFFFFFF

  steam_chars = "23456789BCDFGHJKMNPQRTVWXY"
  final_code = ""
  for _ in range(5):
    code, remainder = divmod(code, len(steam_chars))
    final_code += steam_chars[remainder]

  return final_code


def steam_login(
  login: str,
  password: str,
  shared_secret: str,
  settings: UserSettings,
):
  subprocess.Popen(
    build_runner_launch_args(login, settings),
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    | subprocess.DETACHED_PROCESS,
    close_fds=True,
  )

  autoit.auto_it_set_option("WinTitleMatchMode", 2)
  while not autoit.win_exists("Войти в Steam"):
    logger.debug(f"[{login}] Waiting for Steam window")
    time.sleep(1)
  time.sleep(5)

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
  code = generate_2fa_code(shared_secret)
  logger.info(f"2FA code: {code}")
  pyautogui.typewrite(code)
  pyautogui.press("enter")
  logger.debug(f"[{login}] Guard code typed")


def launch_account(
  account: Account, settings: UserSettings, accounts: list[RunningAccount]
) -> bool:
  login = account.login
  try:
    logger.info(f"launching {login}...")

    steam_login(
      login=login,
      password=account.password,
      shared_secret=account.shared_secret,
      settings=settings,
    )
  # TODO
  finally:
    return False
