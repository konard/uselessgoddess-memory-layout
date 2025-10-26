import asyncio
from typing import List

from steam import TradeOffer
import steam

import states

from core.panel.state import State
from src.core.context import Context
from src.core.account import Account
from src.core.logging import get_logger


logger = get_logger("state.loot")

import asyncio
from steam.ext import csgo

class SendTrade(csgo.Client):

    target_trade_url: steam.utils.TradeURLInfo

    def __init__(self, target_trade_url: str):
      super().__init__()
      self.target_trade_url = steam.utils.parse_trade_url(target_trade_url)
      self.completion_future = asyncio.Future()

    async def on_ready(self):

        logger.info("Logged in as %s", self.user.name)

        target_friend = await self.fetch_user(self.target_trade_url.id.id64)

        if not target_friend:
            logger.error(f"Friend with ID {self.target_trade_url.id.id64} not found in client's cache.")
            return

        logger.info(f"Found target friend: {target_friend.name}")

        logger.info("Fetching your CS:GO inventory...")

        try:
            my_inventory = await self.user.inventory(steam.CSGO)
            logger.info(f"Fetched inventory with {len(my_inventory)} items.")
        except Exception as e:
            logger.error(f"Failed to fetch inventory: {e}")
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
            message="сосал ? Только честно", 
            token=self.target_trade_url.token  
        )


        logger.info(f"Attempting to send trade offer to {target_friend.name}...")
        try:
            await target_friend._send_trade(trade=trade_offer)
            self.completion_future.set_result("Trade offer sent!") 
        except Exception as e:
            logger.error(f"Failed to send trade offer: {e}")  
            
class TradeAccounts(State):
  def __init__(self, accounts: List[Account]):
    self.accounts = accounts

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
        if send_trade_client.is_ready():
          await send_trade_client.close()
        await asyncio.sleep(2)

    return states.Idle()
