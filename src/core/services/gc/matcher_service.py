from __future__ import annotations

from typing import Tuple
import asyncio

from steam.ext.csgo.protobufs.cstrike import MatchmakingClientReserve

from core.account import Account
from core.logging import get_logger
from core.services.gc.gc_parser import decode_gc_bytes

logger = get_logger("sv.matcher")


class MatcherService:
  matches: dict[str, Tuple[int, asyncio.Event]] = {}

  async def get_match_id(self, account: Account):
    if account.login not in self.matches:
      new_event = asyncio.Event()
      self.matches[account.login] = (None, new_event)

    match, event = self.matches[account.login]

    await event.wait()
    event.clear()

    return match

  def set_match_id(self, login: str, match_id: int | None):
    if match_id is None:
      return

    if login in self.matches:
      _, event = self.matches[login]
      self.matches[login] = (match_id, event)
      event.set()
    else:
      event = asyncio.Event()
      event.set()
      self.matches[login] = (match_id, event)

    return True

  def process_message(self, data: bytes, login: str):
    decoded_message = MatchmakingClientReserve().parse(data[4:])
    match_id = decoded_message.reservation.match_id

    logger.trace(f"match_id from message {match_id} for {login}")
    self.set_match_id(login, match_id)

  async def wait_for_match_id(self, accounts: list[Account]):
    self.matches.clear()

    tasks = {
      asyncio.create_task(self.get_match_id(account)): account.login
      for account in accounts
    }

    matches = {}
    pending_tasks = set(tasks.keys())

    try:
      first_match_received = False

      while pending_tasks:
        if not first_match_received:
          logger.trace("Waiting for first match_id (no timeout)...")
          done, pending_tasks = await asyncio.wait(
            pending_tasks, return_when=asyncio.FIRST_COMPLETED
          )
        else:
          logger.trace("Waiting for next match_id (3s timeout)...")
          done, pending_tasks = await asyncio.wait(
            pending_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=3.0
          )

          if not done:
            for task in pending_tasks:
              task.cancel()
            logger.error(
              "Timeout waiting for next match_id: no events received in 3 seconds"
            )
            return False

        for task in done:
          login = tasks[task]
          match_id = await task
          matches[login] = match_id

          logger.trace(
            f"Got match_id {match_id} for {login} ({len(matches)}/{len(tasks)})"
          )

          if not first_match_received:
            first_match_received = True
            logger.trace(
              "First match_id received! Now using 3s timeout for remaining matches."
            )
          else:
            first_match_id = next(iter(matches.values()))
            if match_id != first_match_id:
              for remaining_task in pending_tasks:
                remaining_task.cancel()
              return False

      logger.trace(f"Successfully got all match_ids: {matches}")
      return True

    except Exception as e:
      for task in pending_tasks:
        task.cancel()

      logger.error(f"Failed to get match_ids: {e}")
      return False
