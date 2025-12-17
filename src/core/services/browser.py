import asyncio
import logging
import urllib.parse
from typing import Tuple

from core.account.model import Account
from steam.client import Client

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger("browser")


class BrowserService:
  @staticmethod
  async def launch_browser(account: Account) -> Tuple[bool, str]:
    cookies = {}
    client = Client()

    # --- PHASE 2: Steam Login Attempt ---
    try:
      logger.info(f"Logging in to Steam as {account.login}...")

      try:
        await asyncio.wait_for(
          client.login(
            username=account.login,
            password=account.password,
            shared_secret=account.shared_secret,
          ),
          timeout=15.0,
        )
      except asyncio.TimeoutError:
        logger.warning("Steam login timed out! Launching without auto-login.")
        # Запускаем браузер без кук (в отдельном потоке)
        return await asyncio.to_thread(
          BrowserService._launch_chrome_sync, cookies, None
        )

      logger.info("Login successful. Extracting cookies...")

      if client.user.id64 and client._state.ws:
        try:
          token = client._state.ws.access_token
          if asyncio.iscoroutine(token):
            token = await token
          elif asyncio.iscoroutinefunction(token):
            token = await token()

          if token:
            steam_login_secure = urllib.parse.quote(
              f"{client.user.id64}||{token}"
            )
            cookies["steamLoginSecure"] = steam_login_secure
            cookies["sessionid"] = str(client.http.session_id)
        except Exception as e:
          logger.warning(f"Failed to generate steamLoginSecure: {e}")

      if hasattr(client, "http") and hasattr(client.http, "_session"):
        for cookie in client.http._session.cookie_jar:
          cookies[cookie.key] = cookie.value

      if not cookies:
        logger.warning("No cookies found. Launching without auto-login.")

    except Exception as e:
      logger.error(f"Login exception: {e}")
    finally:
      await client.close()

    steam_id = client.user.id if client.user else None
    return await asyncio.to_thread(
      BrowserService._launch_chrome_sync, cookies, steam_id
    )

  @staticmethod
  def _launch_chrome_sync(
    cookies: dict, steam_id: int | None
  ) -> Tuple[bool, str]:
    """Синхронный запуск Selenium (должен выполняться в отдельном потоке)"""
    try:
      logger.info("Launching Chrome...")
      chrome_options = Options()
      chrome_options.add_experimental_option("detach", True)
      chrome_options.add_argument("--log-level=3")

      service = Service(ChromeDriverManager().install())
      driver = webdriver.Chrome(service=service, options=chrome_options)

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
            logger.warning(f"CDP error (community): {e}")

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
            logger.warning(f"CDP error (store): {e}")

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
