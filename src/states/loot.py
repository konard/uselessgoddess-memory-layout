import asyncio
import json
from pathlib import Path
from typing import Any

from steam.ext import csgo
from steam.ext.csgo.price_analizator.assembler import (
  SkinAssembler,
  load_csgo_english,
  load_items_game,
)

import states
from core.account import Account
from core.context import Context
from core.logging import get_logger
from core.panel import State
from ui.widgets import Label, Progress
from utils.client_login_wrapper import client_login_wrapper

logger = get_logger("state.loot")

prices = json.loads(Path("data/price.json").read_text(encoding="utf-8"))
assembler = SkinAssembler(
  load_items_game(Path("data/items_game.txt")),
  load_csgo_english(Path("data/csgo_english.json")),
  prices=prices,
)


class ClaimDrop(csgo.Client):
  def __init__(self, account: Account):
    super().__init__()
    self.account = account
    self.completion = asyncio.Future()
    self.loot_report = None

  async def on_weekly_reward(self, items: list[csgo.BaseItem]):
    results: list[dict[str, Any]] = []
    print("on_weekly_reward")
    global_stats = self.user.global_statistics
    rtime32_cur = self.user.gc_client_msg.rtime32_gc_welcome_timestamp

    if rtime32_cur == 0:
      logger.debug("looting")
      return

    if self.loot_report is not None:
      self.completion.set_result(self.loot_report)
      return

    if rtime32_cur == -1:
      self.completion.set_result("No weekly reward available")
      return

    if global_stats:
      for item in items:
        result = assembler.assemble_item(item)
        results.append(result)

      filtered = filter(
        lambda x: x.get("price", -1) > 0 and x.get("tradable_after", 1) == 0,
        results,
      )

      sorted_results = sorted(filtered, key=lambda x: x.get("price", -1), reverse=True)
      top_results = sorted_results[:2]

      report_results = [
        f"{report['item_name']} {report['price']}$" for report in top_results
      ]
      self.loot_report = report_results
      await self.redeem_weekly_reward(
        [int(item["id"]) for item in top_results], time=rtime32_cur
      )


async def claim_drop(parent, account: Account):
  loot_client = ClaimDrop(account)

  try:
    login_task = parent.spawn(
      client_login_wrapper(loot_client, account),
    )

    done, pending = await asyncio.wait(
      [login_task, loot_client.completion],
      return_when=asyncio.FIRST_COMPLETED,
      timeout=60.0,
    )

    for task in pending:
      task.cancel()

    if loot_client.completion in done:
      result = await loot_client.completion
      logger.info(f"[{account.login}]: {result}")
    elif login_task in done:
      await login_task
      logger.error(
        f"[{account.login}] Login task finished unexpectedly without reward event."
      )
    else:
      logger.warn(f"[{account.login}] Operation timed out.")
  except Exception as e:
    logger.error(f"Failed to process account {account.login}: {e}")
    import traceback

    logger.error(traceback.format_exc())

  finally:
    await loot_client.close()
    await asyncio.sleep(2)


class LootAccounts(State):
  def __init__(self, accounts: list[Account]):
    self.accounts = accounts

  def layout(self, ctx: Context, dispatch):
    self.progress = Progress(len(self.accounts))

    return [Label("Looting progress"), self.progress]

  async def execute(self, ctx: Context):
    for account in self.accounts:
      try:
        await claim_drop(self, account)
      except Exception as e:
        logger.error(f"Failed to process account {account.login}: {e}")

        import traceback

        logger.error(traceback.format_exc())
      finally:
        self.progress.inc()
        await asyncio.sleep(2)

    return states.ScanAccounts(self.accounts, trade=True)
