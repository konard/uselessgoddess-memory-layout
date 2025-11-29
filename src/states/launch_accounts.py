import asyncio
import os

from os.path import isdir, isfile

from core.account.model import RunningAccount
from core.panel.state import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from core.process_config import ConfigService
from core.services import LaunchService, WindowService
from core import utils
from states.make_lobbies import MakeLobbies

logger = get_logger("state.launch_accounts")


def check_path(path, what: str, dir: bool = False):
  if not path:
    logger.warn(f"You must set path to {what}")

  probe = isdir(path) if dir else isfile(path)
  if not probe:
    logger.error(f"Invalid path to {what} - {path}")
    raise Exception  # mark as return?


MAPS_DIR = "game/csgo/maps"


def remove_bg(dir):
  for file in os.listdir(dir):
    if "_vanity" in file and os.path.isfile(os.path.join(dir, file)):
      os.remove(os.path.join(dir, file))


class LaunchAccounts(State):
  def __init__(self, accounts: list[Account]):
    self.accounts_to_launch = accounts

  async def execute(self, ctx: Context):
    try:
      check_path(ctx.s.u.steam_path, "Steam")
      check_path(ctx.s.u.cs_path, "CS2", dir=True)
    except Exception:
      return

    maps_path = os.path.join(ctx.s.u.cs_path, MAPS_DIR)
    if isdir(maps_path):
      logger.debug(f"remove backgrounds from {maps_path}")
      remove_bg(maps_path)

    config_service = ConfigService(ctx)
    config_service.ensure_cs_cfgs()
    config_service.block_steam_store()
    for account in self.accounts_to_launch:
      logger.info(f"launching account +{account.login}")

      config_service.apply_video_config(account.steam_id)
      running_account: RunningAccount = await utils.block_on(  # noqa: F841 FIXME
        LaunchService.launch_account_with_steam
      )(account, ctx.settings.user, ctx.accounts())
      logger.info(f"{account.login} launched")

    await asyncio.sleep(5)

    if ctx.ss.farm_on_launch:
      return MakeLobbies()
