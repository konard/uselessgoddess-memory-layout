from core.panel.state import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from core.services.launch_service import LaunchService

logger = get_logger("state.launch_accounts")


class LaunchAccounts(State):
  def __init__(self, accounts: list[Account]):
    self.accounts_to_launch = accounts

  async def execute(self, ctx: Context):
    for account in self.accounts_to_launch:
      logger.info(f"launching account +{account.login}")
      LaunchService.launch_account_with_steam(
        account, ctx.settings.user, ctx.accounts()
      )
      logger.info(f"{account.login} launched")
