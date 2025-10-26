import asyncio
from typing import List

import states
from core.panel import State
from core.context import Context
from core.account import Account
from core.logging import get_logger

from steam.ext.csgo import ClaimDrop as BaseClaim
from steam.ext.csgo import BaseItem


logger = get_logger("state.loot")

import asyncio
from typing import Any
from steam.ext import csgo

from steam.ext.csgo.price_analizator.assembler import SkinAssembler

assembler = SkinAssembler()

class ClaimDrop(csgo.Client):

    def __init__(self):
        super().__init__()
        self.completion_future = asyncio.Future()

    async def on_weekly_reward(self, items: list[csgo.BaseItem]):
        results: list[dict[str, Any]] = []
    
        global_stats = self.user.global_statistics
        rtime32_cur = self.user.gc_client_msg.rtime32_gc_welcome_timestamp

        if rtime32_cur == 0:
            print("Looting")
            return

        if rtime32_cur == -1:
            print("No weekly reward available")
            self.completion_future.set_result("No weekly reward available")
            return
    
        if global_stats:
            print(f"rtime32_cur: {rtime32_cur}")
            print(f"items: {items}")
            for item in items:
                result = assembler.assemble_item(item)
                results.append(result)
        
            sorted_results = sorted(results, key=lambda x: x.get('price', -1), reverse=True)
            top_results = sorted_results[:2]
            await self.redeem_weekly_reward([int(item['id']) for item in top_results], time=rtime32_cur)  
            
class LootAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts

  async def execute(self, ctx: Context):
    for account in self.accounts:
      loot_client = ClaimDrop()

      try:
        login_task = asyncio.create_task(
          loot_client.login(
            username=account.login,
            password=account.password,
            shared_secret=account.shared_secret,
            identity_secret=account.identity_secret,
          )
        )

        done, pending = await asyncio.wait(
          [login_task, loot_client.completion_future],
          return_when=asyncio.FIRST_COMPLETED,
          timeout=60.0,
        )

        for task in pending:
          task.cancel()

        if loot_client.completion_future in done:
          result = await loot_client.completion_future
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
          logger.warning(f"[{account.login}] Operation timed out.")
          self.current_status = f"{account.login}: Timeout"
      except Exception as e:
        logger.error(f"Failed to process account {account.login}: {e}")
        self.current_status = f"{account.login}: Failure"

      finally:
        if loot_client.is_ready():
          await loot_client.close()
        await asyncio.sleep(2)

    return states.Idle()
