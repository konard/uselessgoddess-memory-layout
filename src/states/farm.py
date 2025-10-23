import asyncio
from typing import List
from dataclasses import dataclass, field
from src.core.panel import Message, State
from src.core.context import Context
from src.core.accounts import Account
from src.core.logging import get_logger

logger = get_logger("state.farm")

@dataclass
class StopFarming(Message):
  pass


class LaunchAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts

  async def execute(self, ctx: Context) -> State:
    for account in self.accounts:
      logger.info(f"launching account +{account.login}")
      await asyncio.sleep(1)
      logger.info(f"{account.login} launched")

    logger.info("all accounts launched")

    while True:
      await asyncio.sleep(1)
