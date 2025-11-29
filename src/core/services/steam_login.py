import time
import base64
import subprocess
import pyautogui
import struct
import hmac

from pyzbar.pyzbar import decode

from core.logging import get_logger
from core.services import UserSettings
from core.services.windows_service import WindowService

logger = get_logger("sv.launch")


def build_runner_launch_args(login: str, settings: UserSettings):
  args = [
    "py",
    "src\\utils\\cs_runner\\matchid_sender.py",
    "--steamPath",
    settings.steam_path,
    "--login",
    login,
  ]

  logger.debug(f"run runner with args: {args}")

  return args


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

  while not WindowService.wait_for_window("Войти в Steam", 10):
    logger.debug(f"[{login}] Waiting for Steam window")
    time.sleep(1)
  time.sleep(5)

  if not login_qr(login, password, shared_secret, settings):
    logger.warn("failed to login. run fallback")
    login_fallback(login, password, shared_secret, settings)


def wait_qr() -> str:
  qr_url = None

  while True:
    screenshot = pyautogui.screenshot()
    codes = decode(screenshot)

    for code in codes:
      data = code.data.decode("utf-8")
      if "s.team" in data:
        qr_url = data
        break

    if qr_url:
      logger.debug(f"found QR code: {qr_url}")
      break
    time.sleep(1)

  return qr_url


def login_qr(
  login: str,
  password: str,
  shared_secret: str,
  settings: UserSettings,
):
  qr_url = wait_qr()
  code = subprocess.run(
    [
      "node",
      # todo!: better to use `scripts("script.js")`
      "resources/scripts/approve_qr.js",
      login,
      password,
      shared_secret,
      qr_url,
    ],
    text=True,
  ).returncode

  return code == 0


def login_fallback(
  login: str, password: str, shared_secret: str, settings: UserSettings
):
  logger.debug(f"[{login}] Steam launched")
  pyautogui.typewrite(login)
  logger.debug(f"[{login}] Login typed")
  pyautogui.press("tab")
  logger.debug(f"[{login}] Tab pressed")
  pyautogui.typewrite(password)
  logger.debug(f"[{login}] Password typed")
  pyautogui.press("enter")
  logger.debug(f"[{login}] Enter pressed")

  while pyautogui.locateOnScreen("resources/img/log-ru.jpg", confidence=0.9):
    logger.debug(f"[{login}] Waiting for Guard window")
    time.sleep(1)

  logger.debug(f"[{login}] Credentials typed")
  code = generate_2fa_code(shared_secret)
  logger.info(f"2FA code: {code}")
  pyautogui.typewrite(code)
  pyautogui.press("enter")
  logger.debug(f"[{login}] Guard code typed")
