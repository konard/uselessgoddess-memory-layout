"""
LaunchService - сервис для запуска аккаунтов
"""

from typing import List
import time

from core.account.model import RunningAccount
from core.logging import get_logger
from core.account import Account
from core.services.account import AccountsService
from core.services.cs_controller import CS2Controller
from core.services.steam_login import steam_login
from core.services.windows_service import WindowService
from utils import steam_web_helper_limiter
from src.core.services import UserSettings

logger = get_logger("yacs.launch")


class LaunchService:
  """Сервис для запуска аккаунтов"""

  @staticmethod
  def launch_account_with_steam(
    account: Account, settings: UserSettings, accounts: List[Account]
  ) -> bool:
    """Запустить аккаунт через Steam"""
    try:
      steam_login(
        login=account.login,
        password=account.password,
        shared_secret=account.shared_secret,
        settings=settings,
      )

      if LaunchService._launch_cs2(account, accounts):
        return True

    except Exception as ex:
      if str(ex) == "run program failed":
        logger.error(
          "\nНе правильно указан путь до steam.exe!\nИзмените в настройках.\n"
        )
        logger.error(f"[{account.login}] run program failed. Check steam_path")
      else:
        logger.exception(
          f"[{account.login}] Unexpected exception during launching account"
        )
        logger.error(str(ex))
      return False

  @staticmethod
  def _launch_cs2(account: Account, accounts: List[Account]) -> bool:
    try:
      logger.debug(f"[{account.login}] Waiting for CS window after launch...")
      counter_strike_2_title = "Counter-Strike 2"

      running_account = RunningAccount(
        login=account.login,
        password=account.password,
        shared_secret=account.shared_secret,
        identity_secret=account.identity_secret,
        steam_id=account.steam_id,
        posX=0,
        posY=0,
      )
      while not WindowService.wait_for_window(
        counter_strike_2_title, timeout_sec=10
      ):
        steam_web_helper_limiter.limit_steam_web_helper(
          force_close=True, white=["Steam"]
        )
        WindowService.focus_window("Steam")
        CS2Controller.click_if_exists(
          "resources/img/run_any_way.png", running_account, 0.9, True, True
        )

      while (
        WindowService.rename_window(
          counter_strike_2_title,
          running_account.win_cs_title,
        )
        is None
      ):
        time.sleep(1)

      WindowService.wait_for_window(
        running_account.win_cs_title, timeout_sec=10
      )

      next_x, next_y = WindowService.get_next_window_position(accounts)

      running_account.posX = next_x
      running_account.posY = next_y

      WindowService.move_window_to_position(
        running_account.win_cs_title, next_x, next_y
      )

      logger.info(f"+ Аккаунт {account.login} успешно запущен!")

      steam_web_helper_limiter.limit_steam_web_helper(force_close=True)

      return running_account

    except Exception:
      logger.exception(f"[{account.login}] Ошибка при запуске CS2")
      return False

  @staticmethod
  def close_account(account_data: Account) -> None:
    """Закрыть аккаунт"""
    logger.info(f"[{account_data.login}] Closing account processes")
    AccountsService.stop_account(account_data.login)
