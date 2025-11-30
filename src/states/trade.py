import json
import asyncio
from typing import List, Any, Optional

import steam
from steam.ext import csgo
from steam import TradeOffer

from core.account.lock import AccountsLock
from core.account.model import FarmStatus
from core.panel.state import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
import states
from ui.widgets import Label, Progress

logger = get_logger("state.trade")


class ScanInventory(steam.Client):
  trade_url: steam.utils.TradeURLInfo

  def __init__(self, trade_url: Optional[str], account_lock: AccountsLock):
    super().__init__()
    self.account_lock = account_lock
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
          logger.warning(f"Could not fetch price for {item.name}: {e}")

    if not items_to_send:
      if not self.complete.done():
        self.account_lock.set_field(self.username, "status", FarmStatus.TRADED)
        self.complete.set_result(("No tradable item in inventory", []))

      return

    try:
      if self.identity_secret is not None:
        count = 0
        while count < 5:
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
            break
          except Exception as e:
            logger.error(
              f"Failed to send trade offer, retry {count + 1}/5 in 10 seconds: {e}"
            )
            await asyncio.sleep(10)
            count += 1

        self.account_lock.set_field(self.username, "status", FarmStatus.TRADED)
        if not self.complete.done():
          self.complete.set_result(("Trade sent", items_to_report))
    except Exception as e:
      logger.error(f"Failed to send trade offer: {e}")
      if not self.complete.done():
        self.complete.set_result(("Drop reported", items_to_report))


class ScanAccounts(State):
  def __init__(self, accounts: List[Account], trade: bool = False):
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
    settings = ctx.settings.user

    if not settings.trade_url:
      logger.error("You must set `trade_url` in settings to send loot")
      return

    for account in self.accounts:
      await asyncio.sleep(5)
      send_trade_client = ScanInventory(
        settings.trade_url if self.trade else None,
        ctx.account.lock,
      )

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
          send_trade_client.login(
            **login_data,
            identity_secret=account.identity_secret,
          )
        )

        done, pending = await asyncio.wait(
          [login_task, send_trade_client.complete],
          return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
          task.cancel()

        if send_trade_client.complete in done:
          message, sent_items = await send_trade_client.complete
          logger.info(f"[{account.login}]: {message}")
          self.status.set(f"{account.login}: {message}")

          for data in sent_items:
            name = data["name"]
            price = data["price"]
            if name not in self.trade_report:
              self.trade_report[name] = {"price": price, "amount": 0}
            self.trade_report[name]["amount"] += 1
        elif login_task in done:
          await login_task
          logger.error(
            f"[{account.login}] Login finished unexpectedly without reward event."
          )
          self.status.set(f"{account.login}: Login error")
        else:
          logger.warning(f"[{account.login}] Operation timed out.")
          self.status.set(f"{account.login}: Timeout")
      except Exception as e:
        logger.error(f"Failed to process account {account.login}: {e}")

        import traceback

        print(traceback.format_exc())

        self.status.set(f"{account.login}: Failure")

      finally:
        self.progress.inc()
        if send_trade_client.is_ready():
          await send_trade_client.close()
        await asyncio.sleep(2)

    try:
      with open("report.json", "w", encoding="utf-8") as f:
        json.dump(self.trade_report, f, indent=2, ensure_ascii=False)
      logger.info("Report saved to `report.json`")
      self.status.set("Completed. Report generated.")
    except Exception as e:
      logger.error(f"Failed to write report: {e}")
      self.status.set("Completed.")

    from states.idle import Idle

    return Idle()
