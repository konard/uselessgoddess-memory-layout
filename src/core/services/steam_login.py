import os
import asyncio
import time
import base64
import subprocess
import pyautogui
import struct
import hmac
import pyperclip
import sys

import io
from core.account.model import Account
from core.services.cs_controller import CS2Controller, ZeroPosAccount
import resources

import numpy as np
import zxingcpp
from steam import Client
from PIL import Image


from core.logging import get_logger
from core.services.settings import UserSettings
from core.services.api.api_controller import api_controller
from core.services.api.free_fames_response import FreeGamesResponse
from core.services.windows_service import WindowService

from constants import PROJECT_ROOT
from utils import steam_web_helper_limiter

logger = get_logger("sv.launch")


def build_runner_launch_args(login: str, settings: UserSettings):
  runner_args = ["cs2_runner.exe"]

  runner_args.extend(
    [
      "--steamPath",
      settings.steam_path,
      "--login",
      login,
      "--hook_dll",
      f"{os.getcwd()}/data/NetHook2.dll",
    ]
  )

  if settings.experimental_launch:
    runner_args.append("--experimental")

  logger.debug(f"Runner args: {runner_args}")
  return runner_args


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
  account: Account,
  settings: UserSettings,
):
  args = build_runner_launch_args(account.login, settings)

  proc = subprocess.Popen(
    args,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    | subprocess.DETACHED_PROCESS,
    close_fds=True,
  )

  logger.debug(
    f"[{account.login}] Process started. Entering monitoring loop..."
  )

  login_window_title = "Войти в Steam"
  game_window_title = "Counter-Strike 2"
  renamed_game_title = f"[{account.login}] # CS"

  last_log_time = time.time()

  found_qr = None

  while True:
    steam_web_helper_limiter.limit_steam_web_helper(
      force_close=True,
      white=["Steam"],
      window_title_blacklist=[
        "Список друзей",
        "Список игр",
        "Специальные предложения",
      ],
    )

    if proc.poll() is not None and proc.returncode != 0:
      logger.error(
        f"[{account.login}] Process crashed/closed with code {proc.returncode}"
      )
      break

    if WindowService.window_exists(game_window_title):
      logger.info(
        f"[{account.login}] Game window '{game_window_title}' detected! Success."
      )
      return proc.pid

    if WindowService.window_exists(renamed_game_title):
      logger.info(
        f"[{account.login}] Renamed game window detected. Already running."
      )
      return proc.pid

    if WindowService.window_exists("Steam"):
      CS2Controller.click_if_exists(
        "img/run_any_way.png", ZeroPosAccount(), 0.9, True, True
      )
      time.sleep(0.2)
      CS2Controller.click_if_exists(
        "img/asf_farming.png", ZeroPosAccount(), 0.9, True, True
      )

    if WindowService.window_exists(login_window_title) and found_qr is None:
      found_qr = wait_qr(account.login, timeout=5)

      if found_qr:
        logger.info(
          f"[{account.login}] Valid QR found. Attempting login sequence..."
        )
        if _perform_login_with_qr_url(account, settings, found_qr):
          logger.info(f"[{account.login}] Login submitted.")
        else:
          logger.warn(
            f"[{account.login}] Login attempt failed, retrying loop..."
          )
      else:
        pass

    if time.time() - last_log_time > 30:
      logger.debug(f"[{account.login}] Waiting for Game Window...")
      last_log_time = time.time()

    time.sleep(1)

  return proc.pid


def _perform_login_with_qr_url(account: Account, settings, qr_url):
  loop = asyncio.ProactorEventLoop()
  asyncio.set_event_loop(loop)
  try:
    return loop.run_until_complete(
      _async_login_qr(account, settings, qr_url, loop)
    )
  except Exception as e:
    logger.error(f"Login error: {e}")
    return False
  finally:
    loop.close()


def wait_qr(login: str, timeout: int = 5) -> str | None:
  qr_url = None
  start = time.time()

  game_titles = ["Counter-Strike 2", f"[{login}] # CS"]

  while time.time() - start < timeout:
    for title in game_titles:
      if WindowService.window_exists(title):
        logger.info(
          f"[{login}] Game window detected inside wait_qr! Aborting QR search."
        )
        return None

    try:
      screenshot = pyautogui.screenshot()
      img_array = np.array(screenshot)
      codes = zxingcpp.read_barcodes(img_array)
      for code in codes:
        data = code.text
        if "s.team" in data:
          qr_url = data
          break
    except Exception:
      pass

    if qr_url:
      logger.debug(f"[{login}] QR code found: {qr_url}")
      return qr_url

    time.sleep(1)

  return None  # Timeout


class QRLogin(Client):
  def __init__(self, qr_url, settings):
    super().__init__()
    self.qr_url = qr_url
    self.settings = settings
    self.completion = asyncio.Future()

  async def on_login(self):
    try:
      await self.approve_qr_login(self.qr_url)
      if not self.completion.done():
        self.completion.set_result(True)
    except Exception as e:
      logger.error(f"Failed to approve QR: {e}")
      if not self.completion.done():
        self.completion.set_result(False)
    finally:
      await self.close()


async def _async_login_qr(account: Account, settings, qr_url, loop):
  client = QRLogin(qr_url, settings)

  login_task = loop.create_task(
    client.login(
      username=account.login,
      password=account.password,
      shared_secret=account.shared_secret,
    )
  )

  try:
    done, pending = await asyncio.wait(
      [login_task, client.completion],
      return_when=asyncio.FIRST_COMPLETED,
      timeout=60.0,
    )

    for task in pending:
      task.cancel()

    if client.completion in done:
      return client.completion.result()

    logger.error("Login timed out or failed without completion")
    return False

  except Exception as e:
    logger.error(f"Exception during async login: {e}")
    return False


def login_qr(
  login: str,
  password: str,
  shared_secret: str,
  settings: UserSettings,
):
  qr_url = wait_qr()
  if not qr_url:
    return False

  # Explicitly use ProactorEventLoop on Windows to ensure standard behavior
  loop = asyncio.ProactorEventLoop()
  asyncio.set_event_loop(loop)
  try:
    return loop.run_until_complete(
      _async_login_qr(login, password, shared_secret, settings, qr_url, loop)
    )
  finally:
    loop.close()


def paste_text(text):
  pyperclip.copy(text)
  pyautogui.hotkey("ctrl", "v")  # SUCK MACOS USERS


def load_image(path: str) -> Image.Image:
  return Image.open(io.BytesIO(resources.load(path)))


def login_fallback(
  login: str, password: str, shared_secret: str, settings: UserSettings
):
  logger.debug(f"[{login}] Steam launched")
  paste_text(login)
  logger.debug(f"[{login}] Login pasted")
  pyautogui.press("tab")

  logger.debug(f"[{login}] Tab pressed")
  paste_text(password)
  logger.debug(f"[{login}] Password pasted")
  pyautogui.press("enter")
  logger.debug(f"[{login}] Enter pressed")

  while pyautogui.locateOnScreen(load_image("img/log-ru.jpg"), confidence=0.9):
    logger.debug(f"[{login}] Waiting for Guard window")
    time.sleep(1)

  logger.debug(f"[{login}] Credentials typed")
  code = generate_2fa_code(shared_secret)
  logger.info(f"2FA code: {code}")

  paste_text(code)
  pyautogui.press("enter")
  logger.debug(f"[{login}] Guard code pasted")
