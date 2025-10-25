import asyncio
from typing import List
from dataclasses import dataclass, field

from src.ui.widgets import Button
from src.core.panel import Message, State, StateManager, handles
from src.core.context import Context
from src.core.account import Account
from src.core.logging import get_logger

from states import LaunchAccounts

logger = get_logger("state.loot")

import asyncio
from typing import Any
from steam.ext import csgo

from steam.ext.csgo.price_analizator.assembler import SkinAssembler

assembler = SkinAssembler()


class ClaimDrop(csgo.Client):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.completion_future = asyncio.Future()

  async def on_gc_ready(self) -> None:
    logger.info(f"Background logged: {self.user}")

  async def on_weekly_reward(self, items: list[int]):
    results: list[dict[str, Any]] = []

    global_stats = self.user.global_statistics
    rtime32_cur = self.user.gc_client_msg.rtime32_gc_welcome_timestamp

    if rtime32_cur == -1:
      self.completion_future.set_result("No weekly reward available")
      return

    if global_stats:
      # rtime32_cur = global_stats.rtime32_cur
      logger.debug(f"rtime32_cur: {rtime32_cur}")
      for item in items:
        result = assembler.assemble_item(item)
        results.append(result)

      sorted_results = sorted(results, key=lambda x: x["price"], reverse=True)
      top_results = sorted_results[:2]
      logger.debug(top_results)
      client = await self.redeem_weekly_reward(
        [int(item["id"]) for item in top_results], time=rtime32_cur
      )

      logger.trace(client)


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
