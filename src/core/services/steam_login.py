import os
import asyncio
import time
import base64
import subprocess
import pyautogui
import struct
import hmac
import pyperclip

import io
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

logger = get_logger("sv.launch")


def build_runner_launch_args(login: str, settings: UserSettings):
  args = [
    "cs2_runner.exe",
    "--steamPath",
    settings.steam_path,
    "--login",
    login,
    "--hook_dll",
    f"{os.getcwd()}/data/NetHook2.dll",
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
  proc = subprocess.Popen(
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

  logger.debug("logged in")

  return proc.pid


def wait_qr() -> str:
  qr_url = None

  while True:
    screenshot = pyautogui.screenshot()
    img_array = np.array(screenshot)

    codes = zxingcpp.read_barcodes(img_array)
    for code in codes:
      data = code.text
      if "s.team" in data:
        qr_url = data
        break

    if qr_url:
      logger.debug(f"found QR code: {qr_url}")
      break
    time.sleep(1)

  return qr_url


class QRLogin(Client):
  def __init__(self, qr_url, settings):
    super().__init__()
    self.qr_url = qr_url
    self.settings = settings
    self.completion = asyncio.Future()

  async def on_login(self):
    try:
      # if self.settings.collect_available_steam_games_on_login:
      #   owned_games = await self.user.games()
      #   game_ids: FreeGamesResponse = await api_controller.get(
      #     "/api/cache/steam/free-games"
      #   )
      #   game_ids = filter(lambda x: x.app_id not in owned_games, game_ids)
      await self.approve_qr_login(self.qr_url)
      if not self.completion.done():
        self.completion.set_result(True)
    except Exception as e:
      logger.error(f"Failed to approve QR: {e}")
      if not self.completion.done():
        self.completion.set_result(False)
    finally:
      await self.close()


async def _async_login_qr(
  login, password, shared_secret, settings, qr_url, loop
):
  client = QRLogin(qr_url, settings)

  login_task = loop.create_task(
    client.login(username=login, password=password, shared_secret=shared_secret)
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
