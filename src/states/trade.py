import asyncio
from typing import List

import steam
from steam.ext import csgo
from steam import TradeOffer

from core.panel.state import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from ui.widgets import Label, Progress

logger = get_logger("state.trade")


class SendTrade(csgo.Client):
  trade_url: steam.utils.TradeURLInfo

  def __init__(self, trade_url: str):
    super().__init__()
    self.trade_url = steam.utils.parse_trade_url(trade_url)
    self.completion_future = asyncio.Future()

  async def on_ready(self):
    logger.debug(f"logged in as {self.user.name}")

    target = await self.fetch_user(self.trade_url.id.id64)

    if not target:
      logger.error(
        f"User with ID {self.trade_url.id.id64} not found in client's cache."
      )
      return

    logger.info(f"Found target account: {target.name}")
    logger.info("Fetching your CS inventory...")

    try:
      my_inventory = await self.user.inventory(steam.CSGO)
      logger.info(f"Fetched inventory with {len(my_inventory)} items.")
    except Exception as e:
      self.completion_future.set_result(f"Failed to fetch inventory: {e}")
      return

    item_to_send: list[csgo.Item[csgo.ClientUser]] = []
    for item in my_inventory:
      if item.is_tradable():
        item_to_send.append(item)

    if not item_to_send:
      self.completion_future.set_result("No tradable item in inventory")
      return

    trade_offer = TradeOffer(
      sending=item_to_send,
      receiving=[],
      message="сосал ? Только честно",  # TODO random mesages?
      token=self.trade_url.token,
    )

    logger.info(f"Sending trade offer to {target.name}...")
    try:
      await target._send_trade(trade=trade_offer)
      self.completion_future.set_result("Trade offer sent!")
    except Exception as e:
      logger.error(f"Failed to send trade offer: {e}")


class TradeAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts

  def layout(self, ctx: Context, dispatch):
    self.status = Label()
    self.progress = Progress(len(self.accounts))

    return [
      Label("Send trades to master account"),
      self.progress,
      self.status,
    ]

  async def execute(self, ctx: Context):
    for account in self.accounts:
      send_trade_client = SendTrade(ctx.settings.user.trade_url)

      try:
        login_task = asyncio.create_task(
          send_trade_client.login(
            username=account.login,
            password=account.password,
            shared_secret=account.shared_secret,
            identity_secret=account.identity_secret,
          )
        )

        done, pending = await asyncio.wait(
          [login_task, send_trade_client.completion_future],
          return_when=asyncio.FIRST_COMPLETED,
          timeout=60.0,
        )

        for task in pending:
          task.cancel()

        if send_trade_client.completion_future in done:
          result = await send_trade_client.completion_future
          logger.info(f"[{account.login}]: {result}")
          self.status.set(f"{account.login}: {result}")
        elif login_task in done:
          await login_task
          logger.error(
            f"[{account.login}] Login finished unexpectedly without reward event."
          )
          self.status.set(f"{account.login}: Login error")
        else:
          logger.warning(f"[{account.login}] Operation timed out.")
          self.status.set(f"{account.login}: Timeout")
        self.progress.inc()
      except Exception as e:
        logger.error(f"Failed to process account {account.login}: {e}")
        self.status.set(f"{account.login}: Failure")

      finally:
        if send_trade_client.is_ready():
          await send_trade_client.close()
        await asyncio.sleep(2)
