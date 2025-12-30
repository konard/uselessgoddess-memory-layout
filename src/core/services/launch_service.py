"""
LaunchService - сервис для запуска аккаунтов
"""

import asyncio
import os
import time
from os.path import isdir
from typing import TYPE_CHECKING

from core.account.model import RunningAccount
from core.logging import get_logger

if TYPE_CHECKING:
  from core.context import Context
from core import game_constants, utils
from core.account import Account
from core.process_config import ConfigService
from core.services.account import AccountsService
from core.services.cs_controller import CS2Controller
from core.services.settings import UserSettings
from core.services.windows_service import WindowService
from utils import cs2_terminator, steam_web_helper_limiter

from .steam_login import steam_login

logger = get_logger("launch")

MAPS_DIR = "game/csgo/maps"


def remove_bg(dir):
  for file in os.listdir(dir):
    if "_vanity" in file and os.path.isfile(os.path.join(dir, file)):
      os.remove(os.path.join(dir, file))


class LaunchService:
  """Сервис для запуска аккаунтов"""

  @staticmethod
  async def launch_accounts_with_steam(
    accounts: list[Account], ctx: "Context"
  ) -> list[RunningAccount]:
    maps_path = os.path.join(ctx.s.u.cs_path, MAPS_DIR)
    if isdir(maps_path):
      logger.debug(f"remove backgrounds from {maps_path}")
      remove_bg(maps_path)

    config_service = ConfigService(ctx)
    config_service.ensure_cs_cfgs()
    config_service.block_steam_store()
    running_accounts: list[RunningAccount] = []
    for account in accounts:
      cs2_terminator.close_cs2_mutex()

      logger.info(f"launching account +{account.login}")

      config_service.apply_video_config(account.steam_id)
      running_account: RunningAccount = await utils.block_on(
        LaunchService.launch_account_with_steam
      )(account, ctx.settings.user, ctx.accounts())
      logger.info(f"{account.login} launched")
      await asyncio.sleep(1)
      running_accounts.append(running_account)

    return running_accounts

  @staticmethod
  def launch_account_with_steam(
    account: Account, settings: UserSettings, accounts: list[Account]
  ) -> RunningAccount:
    """Запустить аккаунт через Steam"""
    try:
      logger.debug(f"start account login {account.login}")

      steam_login(
        account=account,
        settings=settings,
      )
      logger.debug(f"account logged in {account.login}")

      return LaunchService._launch_cs2(account, accounts)

    except Exception as ex:
      if str(ex) == "run program failed":
        logger.error("\nНе правильно указан путь до steam.exe!\nИзмените в настройках.\n")
        logger.error(f"[{account.login}] run program failed. Check steam_path")
      else:
        logger.exception(
          f"[{account.login}] Unexpected exception during launching account"
        )
        logger.error(str(ex))
      return False

  @staticmethod
  def _launch_cs2(account: Account, accounts: list[Account]) -> bool:
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
      running_account.lock = account.lock

      while True:
        if WindowService.window_exists(counter_strike_2_title):
          logger.debug(f"[{account.login}] Window found. Killing mutex immediately!")
          cs2_terminator.close_cs2_mutex()
          break
        else:
          steam_web_helper_limiter.limit_steam_web_helper(
            force_close=True,
            white=["Steam"],
            window_title_blacklist=[
              "Список друзей",
              "Список игр",
              "Специальные предложения",
            ],
          )
          time.sleep(0.5)

      logger.debug("window initialization finished")

      time.sleep(15)  # sleep saves all

      while WindowService.window_exists(counter_strike_2_title):
        logger.trace(f"trying to rename window into {running_account.win_cs_title}")

        WindowService.rename_window(
          counter_strike_2_title,
          running_account.win_cs_title,
        )

        time.sleep(1)

      WindowService.wait_for_window(running_account.win_cs_title, timeout_sec=10)

      next_x, next_y = WindowService.get_next_window_position(accounts)

      # -------------------------------------

      stability_start = None
      STABILITY_REQUIRED = 3.0

      while True:
        logger.trace(f"move window to {next_x}:{next_y}")

        info = WindowService.get_window_info(running_account.win_cs_title)
        if not info:
          time.sleep(1)
          continue

        curr_x = info.get("posX")
        curr_y = info.get("posY")

        if curr_x == next_x and curr_y == next_y:
          if stability_start is None:
            stability_start = time.time()

          elapsed = time.time() - stability_start
          if elapsed >= STABILITY_REQUIRED:
            logger.debug(f"[{account.login}] Позиция стабильна ({elapsed:.1f}s).")
            break
          time.sleep(0.5)
        else:
          stability_start = None
          WindowService.move_window_to_position(
            running_account.win_cs_title, next_x, next_y
          )
          time.sleep(0.5)

      # -------------------------------------

      running_account.posX = next_x
      running_account.posY = next_y

      time.sleep(0.5)

      logger.info(f"+ Account {account.login} started!")

      steam_web_helper_limiter.limit_steam_web_helper(force_close=True)

      WindowService.focus_window(running_account.win_cs_title)
      CS2Controller.click(**game_constants.play_button, account=running_account)

      time.sleep(2)

      CS2Controller.wait_for_image("img/play.png", running_account)

      time.sleep(0.5)

      CS2Controller.click_if_exists("img/close_reward.png", running_account, 0.9, True)

      time.sleep(0.5)

      CS2Controller.click_if_exists("img/close.png", running_account, 0.9, True)

      time.sleep(0.5)

      cs2_terminator.close_cs2_mutex()

      return running_account

    except Exception:
      logger.exception(f"[{account.login}] Ошибка при запуске CS2")
      return False
