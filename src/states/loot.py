import asyncio
from typing import List

from src.core.panel import State
from src.core.context import Context
from src.core.account import Account
from src.core.logging import get_logger

from steam.ext.csgo import ClaimDrop as BaseClaim
from steam.ext.csgo import BaseItem


logger = get_logger("state.loot")


class ClaimDrop(BaseClaim):
  def __init__(self):
    super().__init__(self)
    self.completion_future = asyncio.Future()

  async def on_weekly_reward(self, items: list[BaseItem]):
    await super().on_weekly_reward(items)
    self.completion_future.set_result("Result")


class LootAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts

  async def execute(self, ctx: Context):
    for account in self.accounts:
      client = ClaimDrop()

      try:
        login_task = asyncio.create_task(
          client.login(
            username=account.login,
            password=account.password,
            shared_secret=account.shared_secret,
          )
        )

        done, pending = await asyncio.wait(
          [login_task, client.completion_future],
          return_when=asyncio.FIRST_COMPLETED,
          timeout=60.0,
        )

        for task in pending:
          task.cancel()

        if client.completion_future in done:
          result = await client.completion_future
          logger.info(
            f"[{account.login}] Operation finished with result: {result}"
          )
          self.current_status = f"{account.login}: {result}"
        elif login_task in done:
          await login_task
          logger.error(
            f"[{account.login}] Login task finished unexpectedly without reward event."
          )
          self.current_status = f"{account.login}: Login error"
        else:
          logger.warn(f"[{account.login}] Operation timed out.")
          self.current_status = f"{account.login}: Timeout"
      except Exception as e:
        logger.error(f"Failed to process account {account.login}: {e}")
        self.current_status = f"{account.login}: Failure"

      finally:
        if client.is_ready():
          await client.close()
        await asyncio.sleep(2)

    while True:
      await asyncio.sleep(1)
      logger.info("looter loop")
