import asyncio
from typing import List

import states
from core.panel import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from ui.widgets import Progress

logger = get_logger("state.farm")


class LaunchAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts
    self.launched = 0

  def layout(self, ctx: Context, dispatch):
    self.progress = Progress()

    return [self.progress]

  async def execute(self, ctx: Context):
    launched = 0

    for account in self.accounts:
      logger.info(f"launching account +{account.login}")
      await asyncio.sleep(1)
      logger.info(f"{account.login} launched")

      launched += 1
      self.progress.setValue(int(launched / len(self.accounts) * 100))

    logger.info("all accounts launched")
