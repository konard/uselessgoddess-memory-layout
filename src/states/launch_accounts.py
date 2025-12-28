import asyncio
from typing import List

from core import utils
from core.panel import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from core.services.launch_service import LaunchService

logger = get_logger("state.farm")


class LaunchAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts

  async def execute(self, ctx: Context):
    await LaunchService.launch_accounts_with_steam(self.accounts, ctx)
