import asyncio
import json
from os import name
from typing import List, Any

from core.account.lock import AccountsLock
from core.account.model import FarmStatus
from core.panel import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from ui.widgets import Progress, Label
import states
from steam.ext import csgo
from steam.ext.csgo.price_analizator.assembler import SkinAssembler

logger = get_logger("state.loot")

prices = json.load(open("data/price.json", "r", encoding="utf-8"))
assembler = SkinAssembler(prices)


class ClaimDrop(csgo.Client):
  def __init__(self, account_lock: AccountsLock):
    super().__init__()
    self.completion = asyncio.Future()
    self.loot_report = None
    self.account_lock = account_lock

  async def on_gc_ready(self) -> None:
    profile = await self.user.csgo_profile()
    self.account_lock.set_field(self.username, "lvl", profile.level)
    self.account_lock.set_field(
      self.username, "xp", profile.current_xp - 327680000
    )
    self.account_lock.set_field(
      self.username, "vac_banned", bool(profile.vac_banned)
    )
    self.account_lock.set_field(
      self.username, "refresh_token", self.refresh_token
    )

  async def on_weekly_reward(self, items: list[csgo.BaseItem]):
    results: list[dict[str, Any]] = []

    global_stats = self.user.global_statistics
    rtime32_cur = self.user.gc_client_msg.rtime32_gc_welcome_timestamp

    if rtime32_cur == 0:
      logger.debug("looting")
      return

    if self.loot_report is not None:
      self.completion.set_result(self.loot_report)
      self.account_lock.set_field(self.username, "status", FarmStatus.FARMED)
      return

    if rtime32_cur == -1:
      self.completion.set_result("No weekly reward available")
      self.account_lock.set_field(self.username, "status", FarmStatus.FARMED)
      return

    if global_stats:
      for item in items:
        result = assembler.assemble_item(item)
        results.append(result)

      filtered = filter(
        lambda x: x.get("price", -1) > 0 and x.get("tradable_after", 1) == 0,
        results,
      )

      sorted_results = sorted(
        filtered, key=lambda x: x.get("price", -1), reverse=True
      )
      top_results = sorted_results[:2]

      report_results = [
        f"{report['item_name']} {report['price']}$" for report in top_results
      ]
      self.loot_report = report_results
      await self.redeem_weekly_reward(
        [int(item["id"]) for item in top_results], time=rtime32_cur
      )


class LootAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts

  def layout(self, ctx: Context, dispatch):
    self.progress = Progress(len(self.accounts))

    return [Label("Looting progress"), self.progress]

  async def execute(self, ctx: Context):
    for account in self.accounts:
      loot_client = ClaimDrop(ctx.account.lock)

      login_data = None
      if account.lock.refresh_token:
        login_data = {
          "username": account.login,
          "refresh_token": account.lock.refresh_token,
        }
      else:
        login_data = {
          "username": account.login,
          "password": account.password,
          "shared_secret": account.shared_secret,
        }

      try:
        login_task = asyncio.create_task(
          loot_client.login(
            **login_data,
            identity_secret=account.identity_secret,
          )
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
          logger.warning(f"[{account.login}] Operation timed out.")
        self.progress.inc()
      except Exception as e:
        logger.error(f"Failed to process account {account.login}: {e}")

      finally:
        if loot_client.is_ready():
          await loot_client.close()
        await asyncio.sleep(2)

    return states.ScanAccounts(self.accounts, trade=True)
