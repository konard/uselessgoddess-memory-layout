from os.path import isdir, isfile

from core.panel.state import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from core.services.launch_service import LaunchService

logger = get_logger("state.launch_accounts")


def check_path(path, what: str, dir: bool = False):
  if not path:
    logger.warn(f"You must set path to {what}")

  probe = isdir(path) if dir else isfile(path)
  if not probe:
    logger.error(f"Invalid path to {what} - {path}")
    raise Exception  # mark as return?


class LaunchAccounts(State):
  def __init__(self, accounts: list[Account]):
    self.accounts_to_launch = accounts

  async def execute(self, ctx: Context):
    try:
      check_path(ctx.s.u.steam_path, "Steam")
      check_path(ctx.s.u.cs_path, "CS2", dir=True)
    except Exception:
      return

    for account in self.accounts_to_launch:
      logger.info(f"launching account +{account.login}")
      await self.block(LaunchService.launch_account_with_steam)(
        account, ctx.settings.user, ctx.accounts()
      )
      logger.info(f"{account.login} launched")
