import asyncio
from typing import Any

from numpy import random
from steam import Client

import states
from core.account import Account
from core.context import Context
from core.logging import get_logger
from core.panel import State
from core.services.api.api_controller import api_controller
from core.services.api.free_fames_response import FreeGamesResponse
from ui.widgets import Label, Progress
from utils.client_login_wrapper import client_login_wrapper

logger = get_logger("state.collect_free_games")


class FreeGamesClient(Client):
  def __init__(self, free_games: FreeGamesResponse):
    super().__init__()
    self.completion = asyncio.Future()
    self.free_games = free_games

  async def on_login(self):
    try:
      if not self.free_games:
        logger.warn("No free games found in API")
        self.completion.set_result([])
        return

      # Fetch owned games
      owned_app_ids = await self.user.games()
      # Filter games
      # Assuming free_games is a list of dicts
      games_to_add = [g for g in self.free_games if g.get("app_id") not in owned_app_ids]
      results = []
      if not games_to_add:
        logger.info(f"[{self.user.name}] No new free games to add")

      for game in games_to_add:
        pkg_id = game.get("pkg_id")
        name = game.get("name", str(pkg_id))
        try:
          await asyncio.wait_for(self.redeem_package(pkg_id), timeout=2.0)
          logger.info(f"[{self.user.name}] Added {name}")
          # Small delay to be safe
          await asyncio.sleep(0.5 + random.randint(0, 3) * 1.5)
        except Exception:
          pass

      self.completion.set_result(results)

    except Exception as e:
      logger.error(f"Error in on_logged_on: {e}")
      self.completion.set_result(e)
    finally:
      await self.close()


class CollectFreeGames(State):
  def __init__(self, accounts: list[Account]):
    self.accounts = accounts

  def layout(self, ctx: Context, dispatch):
    self.progress = Progress(len(self.accounts))
    return [Label("Collecting free games..."), self.progress]

  async def execute(self, ctx: Context):
    free_games = api_controller.get("/api/cache/steam/free-games")
    for account in self.accounts:
      client = FreeGamesClient(free_games)

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
