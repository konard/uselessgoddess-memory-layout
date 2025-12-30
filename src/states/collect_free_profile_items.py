import asyncio
from typing import Any

import steam
from numpy import random
from steam import Client, enums
from steam.protobufs import loyalty_rewards

import states
from core.account import Account
from core.context import Context
from core.logging import get_logger
from core.panel import State
from core.services.api.api_controller import api_controller
from core.services.api.free_profile_items import (
  FreeProfileItem,
  FreeProfileItemsResponse,
)
from ui.widgets import Label, Progress
from utils.client_login_wrapper import client_login_wrapper

logger = get_logger("state.collect_free_profile_items")


class FreeProfileItemsClient(Client):
  def __init__(self, items: FreeProfileItemsResponse):
    super().__init__()
    self.completion = asyncio.Future()
    self.items = items

  async def on_login(self):
    try:
      if not self.items:
        logger.warn("No free profile items found in API")
        self.completion.set_result([])
        return

      results = []

      inv = await self.user.inventory(steam.STEAM)
      flat_names = [x.name for x in inv.items]
      items_to_redeem = [item for item in self.items if item.name not in flat_names]
      print(items_to_redeem)
      for item in items_to_redeem:
        try:
          req = loyalty_rewards.RedeemPointsRequest(
            defid=item.def_id, expected_points_cost=0
          )

          resp = await self.ws.send_um_and_wait(req)

          if resp.result == enums.Result.OK:
            logger.info(f"[{self.user.name}] Successfully redeemed {item.name}")
            results.append(item.name)
          else:
            logger.error(
              f"[{self.user.name}] Failed to redeem {item.name}: {resp.result}"
            )
          await asyncio.sleep(0.5 + random.randint(0, 3) * 1.5)
        except Exception as e:
          logger.error(f"[{self.user.name}] Failed to process {item.name}: {e}")
      self.completion.set_result(results)

    except Exception as e:
      logger.error(f"Error in on_login: {e}")
      self.completion.set_result(e)
    finally:
      await self.close()


class CollectFreeProfileItems(State):
  def __init__(self, accounts: list[Account]):
    self.accounts = accounts

  def layout(self, ctx: Context, dispatch):
    self.progress = Progress(len(self.accounts))
    return [Label("Collecting free profile items..."), self.progress]

  async def execute(self, ctx: Context):
    # TODO use api

    raw_data = api_controller.get("/api/cache/steam/free-items")
    items = [FreeProfileItem(**x) for x in (raw_data or [])]

    print(items)
    for account in self.accounts:
      client = FreeProfileItemsClient(items)
      try:
        login_task = self.spawn(
          client_login_wrapper(client, account),
        )

        done, pending = await asyncio.wait(
          [login_task, client.completion],
          return_when=asyncio.FIRST_COMPLETED,
          timeout=60.0,
        )

        for task in pending:
          task.cancel()

        if client.completion in done:
          result = await client.completion
          logger.info(f"[{account.login}] Result: {result}")
        elif login_task in done:
          await login_task
          logger.error(f"[{account.login}] Login task finished unexpectedly.")
        else:
          logger.warn(f"[{account.login}] Operation timed out.")

      except Exception as e:
        logger.error(f"Failed to process account {account.login}: {e}")

      finally:
        if client.is_ready():
          await client.close()
        self.progress.inc()
        await asyncio.sleep(1)

    return states.Idle()
