from typing import List
from core import utils
from core.account.model import RunningAccount
from core.panel.state import State
from core.context import Context
from core.logging import get_logger
from core.process_config import ConfigService
from core.services.launch_service import LaunchService
from core.services.windows_service import WindowService

logger = get_logger("state.wait_for_game")


class SelectAccounts(State):
  def __init__(self, target_size: int):
    self.target_size = target_size

  async def execute(self, ctx: Context):
    launched_accounts = WindowService.scan_cs2_windows(ctx.accounts())

    if len(launched_accounts) < self.target_size:
      config_service = ConfigService(ctx)

      accounts_to_launch = ctx.unfarmed_accounts()
      for account in accounts_to_launch[
        : self.target_size - len(launched_accounts)
      ]:
        config_service.apply_video_config(account.steam_id)
        await utils.block_on(LaunchService.launch_account_with_steam)(
          account, ctx.settings.user, ctx.accounts()
        )
      return
    else:
      accounts_to_stop: List[RunningAccount] = launched_accounts.values()[
        : len(launched_accounts) - self.target_size
      ]
      for running_account in accounts_to_stop:
        await running_account.stop_account()
      return
