from core.account import Account
from core.context import Context
from core.logging import get_logger
from core.panel import State
from core.services.launch_service import LaunchService

logger = get_logger("state.farm")


class LaunchAccounts(State):
  def __init__(self, accounts: list[Account]):
    self.accounts = accounts

  async def execute(self, ctx: Context):
    await LaunchService.launch_accounts_with_steam(
      self.accounts, ctx, stop_event=self.cancellation_token
    )

    if self.cancellation_token.is_set():
      return
