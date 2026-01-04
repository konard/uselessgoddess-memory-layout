import asyncio
import contextlib
import json
from typing import Any

import steam
from steam import TradeOffer
from steam.ext import csgo

import states
from core.account import Account
from core.account.model import FarmStatus
from core.context import Context
from core.logging import get_logger
from core.panel.state import State
from core.utils import run_blocking
from ui.widgets import Label, Progress
from utils.client_login_wrapper import client_login_wrapper

logger = get_logger("state.trade")


class ScanInventory(steam.Client):
  trade_url: steam.utils.TradeURLInfo

  def __init__(self, trade_url: str | None, account: Account):
    super().__init__()
    print("initing scan inventory")
    self.account = account
    if trade_url:
      self.trade_url = steam.utils.parse_trade_url(trade_url)
    self.complete = asyncio.Future[tuple[str, list]]()

  async def on_login(self):
    logger.debug(f"logged in as {self.user.name}")

    target = None
    if self.trade_url is not None:
      id64 = self.trade_url.id.id64

    logger.info("fetching inventory...")
    try:
      inventory = await self.user.inventory(steam.CSGO)
      logger.info(f"inventory with {len(inventory)} items.")
    except Exception as e:
      if not self.complete.done():
        self.complete.set_result((f"Failed to fetch inventory: {e}", []))
      return

    items_to_send: list[csgo.Item[csgo.ClientUser]] = []
    items_to_report: list[dict[str, Any]] = []

    for item in inventory:
      if item.is_tradable():
        logger.trace(f"tradable item: {item}")
        items_to_send.append(item)
        try:
          info = await item.price()
          items_to_report.append(
            {
              "name": item.market_hash_name,
              "price": info.lowest_price,
            }
          )
        except Exception as e:
          logger.warn(f"Could not fetch price for {item.name}: {e}")

    if not items_to_send:
      if self.account.lock.status == FarmStatus.CAN_BE_LOOTED:
        self.account.lock.status = FarmStatus.TRADED
      self.complete.set_result(("No tradable item in inventory", []))
      return

    if self.identity_secret is not None:
      try:
        logger.info(f"Sending trade offer to {id64}")
        trade_offer = TradeOffer(
          sending=items_to_send,
          receiving=[],
          message="random message",
          token=self.trade_url.token,
        )

        target = await self.fetch_user(id64)
        await target.send(trade=trade_offer)

        if self.account.lock.status == FarmStatus.CAN_BE_LOOTED:
          self.account.lock.status = FarmStatus.TRADED
        if not self.complete.done():
          self.complete.set_result(("Trade sent", items_to_report))

      except Exception as e:
        logger.error(f"Failed to send trade offer: {e}")
        if not self.complete.done():
          self.complete.set_result(("Trade failed", items_to_report))
    else:
      self.complete.set_result(("No idenity_secret set", items_to_report))


async def process_trade(
  parent, account: Account, trade_url: str | None
) -> tuple[str, list[dict[str, Any]]]:
  print("processing trade")
  send_trade_client = ScanInventory(trade_url, account)

  try:
    print("logging in")
    login_task = parent.spawn(client_login_wrapper(send_trade_client, account))

    print("waiting for login")
    done, pending = await asyncio.wait(
      [login_task, send_trade_client.complete],
      return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
      task.cancel()

    if pending:
      with contextlib.suppress(Exception):
        await asyncio.gather(*pending, return_exceptions=True)

    if send_trade_client.complete in done:
      return await send_trade_client.complete
    elif login_task in done:
      await login_task
      logger.error(f"[{account.login}] Login finished unexpectedly without reward event.")
      return "Login error", []
    else:
      logger.warn(f"[{account.login}] Operation timed out.")
      return "Timeout", []
  except Exception as e:
    logger.error(f"Failed to process account {account.login}: {e}")
    import traceback

    print(traceback.format_exc())
    return "Failure", []
  finally:
    if send_trade_client.is_ready():
      await send_trade_client.close()


class ScanAccounts(State):
  def __init__(self, accounts: list[Account], trade: bool = False):
    self.accounts = accounts
    self.trade_report = {}
    self.trade = trade

  def layout(self, ctx: Context, dispatch):
    self.status = Label()
    self.progress = Progress(len(self.accounts))

    return [
      Label("Send trades to master account"),
      self.progress,
      self.status,
    ]

  async def execute(self, ctx: Context):
    from states.idle import Idle

    settings = ctx.settings.user

    if not settings.trade_url:
      logger.error("You must set `trade_url` in settings to send loot")
      return Idle()

    for account in self.accounts:
      await asyncio.sleep(5)
      print("processing trade")
      message, sent_items = await process_trade(
        self, account, settings.trade_url if self.trade else None
      )

      if message == "Trade failed":
        logger.warn(f"[{account.login}]: Trade failed, appending to queue")
        self.status.set(f"{account.login}: Trade failed, retrying later")
        self.accounts.append(account)
        self.progress.limit = len(self.accounts)

      else:
        if message not in ["Login error", "Timeout", "Failure"]:
          logger.info(f"[{account.login}]: {message}")

        self.status.set(f"{account.login}: {message}")

        for data in sent_items:
          name = data["name"]
          price = data["price"]
          if name not in self.trade_report:
            self.trade_report[name] = {"price": price, "amount": 0}
          self.trade_report[name]["amount"] += 1

      self.progress.inc()
      await asyncio.sleep(2)

    try:
      await run_blocking(self._save_report_sync)
      logger.info("Report saved to `report.json`")
      self.status.set("Completed. Report generated.")
    except Exception as e:
      logger.error(f"Failed to write report: {e}")
      self.status.set("Completed.")

    return Idle()

  def _save_report_sync(self):
    with open("report.json", "w", encoding="utf-8") as f:
      json.dump(self.trade_report, f, indent=2, ensure_ascii=False)
