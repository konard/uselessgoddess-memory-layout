from core.panel.state import State
from core.context import Context
from core.account import Account
from core.logging import get_logger

logger = get_logger("state.wait_for_game")


class WaitForGame(State):
  def __init__(self, accounts: list[Account]):
    self.accounts = accounts
    self.launched = 0

  async def execute(self, ctx: Context):
    logger.info(f"Waiting for match_id for {len(self.accounts)} accounts")

    if not await ctx.gc.wait_for_match_id(self.accounts):
      logger.error("Failed to get match_id for all accounts")
      return
