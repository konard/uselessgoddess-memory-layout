from os.path import isdir, isfile

from core.account import Account
from core.context import Context
from core.logging import get_logger
from core.panel.state import State
from core.services import LaunchService
from states.make_lobbies import MakeLobbies

logger = get_logger("state.launch_accounts")


def check_path(path, what: str, dir: bool = False):
  if not path:
    logger.warn(f"You must set path to {what}")

  probe = isdir(path) if dir else isfile(path)
  if not probe:
    logger.error(f"Invalid path to {what} - {path}")
    raise Exception  # mark as return?


class StartFarm(State):
  def __init__(self, accounts: list[Account]):
    self.accounts_to_launch = accounts

  async def execute(self, ctx: Context):
    try:
      check_path(ctx.s.u.steam_path, "Steam")
      check_path(ctx.s.u.cs_path, "CS2", dir=True)
    except Exception:
      return

    await LaunchService.launch_accounts_with_steam(
      self.accounts_to_launch, ctx, stop_event=self.cancellation_token
    )

    if self.cancellation_token.is_set():
      return

    if not ctx.gc.all_connected(self.accounts_to_launch):
      logger.error(
        """Not all accounts connected to GC.\n
               This usually means that you 
               are using an older version of Steam (32-bit), 
               but very rarely there may be false alarms, 
               if the panel accepts an invitation to the lobby, 
               then panel works well."""
      )

    if ctx.ss.farm_on_launch:
      return MakeLobbies(None)
