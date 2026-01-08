import asyncio
import contextlib
import io
import os
import time
import urllib.parse
import zipfile
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service
from steam.client import Client

from core.account.model import Account
from core.logging import get_logger
from core.services.settings import SettingsService
from utils.client_login_wrapper import client_login_wrapper
from utils.is_jwt_valid import is_jwt_valid

logger = get_logger("browser")


class BrowserService:
  drivers = []  # Keep references to prevent Garbage Collection closure

  @staticmethod
  def _get_cookies_from_cache(account: Account) -> dict | None:
    try:
      token_info = account.lock.access_token_info
      if token_info and account.steam_id and is_jwt_valid(token_info.get("token", "")):
        logger.info(f"Using cached access token for {account.login}")
        token = token_info["token"]
        return {
          "steamLoginSecure": urllib.parse.quote(f"{account.steam_id}||{token}"),
          "sessionid": os.urandom(12).hex(),
        }
    except Exception as e:
      logger.warn(f"Failed to get cookies from cache: {e}")
    return None

  @staticmethod
  async def _login_and_get_cookies(account: Account) -> dict | None:
    client = Client()
    cookies = {}

    login_task = asyncio.create_task(client_login_wrapper(client, account))

    try:
      logger.info(f"Logging in to Steam as {account.login}...")

      await asyncio.wait_for(login_task, timeout=15.0)

      if client.user.id64 and client._state.ws:
        try:
          token = client._state.ws.access_token
          if asyncio.iscoroutine(token):
            token = await token
          elif asyncio.iscoroutinefunction(token):
            token = await token()

          if token:
            account.lock.access_token_info = {
              "token": token,
              "timestamp": time.time(),
            }
            cookies["steamLoginSecure"] = urllib.parse.quote(
              f"{client.user.id64}||{token}"
            )
            cookies["sessionid"] = str(client.http.session_id)
        except Exception as e:
          logger.warn(f"Failed to extract token/cookies: {e}")

      if (
        client.user
        and hasattr(client, "http")
        and hasattr(client.http, "_session")
        and client.http._session
      ):
        for cookie in client.http._session.cookie_jar:
          cookies[cookie.key] = cookie.value

      return cookies

    except Exception as e:
      logger.error(f"Login failed: {e}")
      return None
    finally:
      if not login_task.done():
        login_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
          await login_task
      with contextlib.suppress(Exception):
        await client.close()

  @staticmethod
  async def launch_browser(
    account: Account, settings_service: SettingsService | None = None
  ) -> tuple[bool, str]:
    if settings_service is None:
      settings_service = SettingsService()
    extension_ids = settings_service.user.extension_ids
    steam_id = account.steam_id

    cookies = BrowserService._get_cookies_from_cache(account)

    if not cookies:
      cookies = await BrowserService._login_and_get_cookies(account)

    if not cookies:
      logger.warn("No cookies found/generated. Launching without auto-login.")

    return await asyncio.to_thread(
      BrowserService._launch_chrome_sync, cookies, steam_id, extension_ids
    )

  @staticmethod
  def _download_and_unpack_extension(extension_id: str) -> str | None:
    """Скачивает и распаковывает расширение по ID из Chrome Web Store."""
    ext_dir = Path("data/extensions")
    ext_dir.mkdir(parents=True, exist_ok=True)

    crx_path = ext_dir / f"{extension_id}.crx"
    unpacked_path = ext_dir / f"{extension_id}_unpacked"

    if unpacked_path.exists() and any(unpacked_path.iterdir()):
      logger.info(f"Extension {extension_id} already unpacked at {unpacked_path}")
      return str(unpacked_path.absolute())

    if not crx_path.exists():
      logger.info(f"Downloading extension {extension_id} from Chrome Web Store...")
      try:
        url = f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=132.0&acceptformat=crx2,crx3&x=id%3D{extension_id}%26uc"
        response = requests.get(url, allow_redirects=True, timeout=30)
        if response.status_code == 200:
          with open(crx_path, "wb") as f:
            f.write(response.content)
          size = crx_path.stat().st_size
          logger.info(f"Extension downloaded. Size: {size} bytes.")
          if size < 1024:
            logger.warn("File too small, deleting.")
            crx_path.unlink()
            return None
        else:
          logger.warn(f"Download failed: {response.status_code}")
          return None
      except Exception as e:
        logger.warn(f"Error downloading: {e}")
        return None

    logger.info(f"Unpacking extension {extension_id}...")
    try:
      unpacked_path.mkdir(exist_ok=True)
      try:
        with zipfile.ZipFile(crx_path, "r") as zip_ref:
          zip_ref.extractall(unpacked_path)
        logger.info("Unzip successful.")
      except zipfile.BadZipFile:
        logger.warn("Standard unzip failed (CRX header?), trying skip...")
        with open(crx_path, "rb") as f:
          data = f.read()
          pos = data.find(b"PK\x03\x04")
          if pos > -1:
            with zipfile.ZipFile(io.BytesIO(data[pos:]), "r") as zip_ref:
              zip_ref.extractall(unpacked_path)
            logger.info("Unzip successful after skipping header.")
          else:
            logger.error("Could not find zip header in CRX.")
            return None

      if (unpacked_path / "_metadata").exists():
        import shutil

        shutil.rmtree(unpacked_path / "_metadata")
        logger.info("Removed _metadata folder.")

      return str(unpacked_path.absolute())
    except Exception as e:
      logger.error(f"Failed to unpack extension: {e}")
      return None

  @staticmethod
  def _prepare_extensions(extension_ids: list[str]) -> str:
    """Скачивает расширения и возвращает строку путей для аргумента --load-extension."""
    paths = []
    for ext_id in extension_ids:
      path = BrowserService._download_and_unpack_extension(ext_id)
      if path:
        paths.append(path)
    return ",".join(paths)

  @staticmethod
  def _launch_chrome_sync(
    cookies: dict, steam_id: int | None, extension_ids: list[str] | None = None
  ) -> tuple[bool, str]:
    """Синхронный запуск Selenium (должен выполняться в отдельном потоке)"""
    try:
      logger.info("Launching Edge...")
      edge_options = EdgeOptions()
      edge_options.add_experimental_option("detach", True)
      edge_options.add_argument("--log-level=3")

      edge_options.enable_bidi = False

      edge_options.add_argument("--no-sandbox")
      edge_options.add_argument("--disable-dev-shm-usage")
      edge_options.add_argument("--remote-allow-origins=*")
      edge_options.add_argument("--enable-unsafe-extension-debugging")

      if extension_ids:
        logger.info(f"Preparing extensions: {extension_ids}")
        ext_paths = BrowserService._prepare_extensions(extension_ids)
        if ext_paths:
          logger.info(f"Loading extensions: {ext_paths}")
          edge_options.add_argument(f"--load-extension={ext_paths}")

      service = Service(
        log_output="edgedriver.log",
        service_args=["--verbose"],
      )
      driver = webdriver.Edge(service=service, options=edge_options)

      # Keep reference to prevent Garbage Collection closure
      BrowserService.drivers.append(driver)

      time.sleep(3)

      if cookies:
        logger.info(f"Injecting {len(cookies)} cookies via CDP...")

        for name, value in cookies.items():
          try:
            driver.execute_cdp_cmd(
              "Network.setCookie",
              {
                "name": name,
                "value": value,
                "domain": ".steamcommunity.com",
                "path": "/",
                "secure": True,
              },
            )
          except Exception as e:
            logger.warn(f"CDP error (community): {e}")

          try:
            driver.execute_cdp_cmd(
              "Network.setCookie",
              {
                "name": name,
                "value": value,
                "domain": ".store.steampowered.com",
                "path": "/",
                "secure": True,
              },
            )
          except Exception as e:
            logger.warn(f"CDP error (store): {e}")

        target_url = "https://steamcommunity.com/my/profile"
        driver.get(target_url)
        return True, "Браузер запущен (Авторизован)"
      else:
        driver.get("https://steamcommunity.com/login/home/?goto=")
        return True, "Браузер запущен (Требуется вход)"

    except Exception as e:
      logger.error(f"Selenium launch error: {e}")
      import traceback

      traceback.print_exc()
      return False, f"Ошибка запуска браузера: {e}"
