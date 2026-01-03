import asyncio
import time
from collections.abc import Coroutine
from typing import Any

from steam import Client

from core.account.model import Account
from core.logging import get_logger
from utils.is_jwt_valid import is_jwt_valid

logger = get_logger("client_login_wrapper")


async def client_login_wrapper(client: Client, account: Account) -> bool:
  try:
    # 1. Setup Token Saving logic (Safe Hook) BEFORE login
    # We capture the original on_login to avoid breaking state classes
    original_on_login = getattr(client, "on_login", None)

    async def wrapped_on_login():
      logger.trace(f"saved access token for {account.login}")
      if client._state.ws and client._state.ws.access_token:
        logger.trace("Access token found")
        token = client._state.ws.access_token
        # Handle async/sync token access
        if asyncio.iscoroutine(token):
          token = await token
        elif asyncio.iscoroutinefunction(token):
          token = await token()

        if token:
          account.lock.access_token_info = {
            "token": token,
            "timestamp": time.time(),
          }
          account.lock.refresh_token = client._state.ws.refresh_token

      if original_on_login:
        await original_on_login()

    # Override the handler on this instance
    client.on_login = wrapped_on_login

    # 2. Perform Login (Blocking - runs the loop)
    refresh_token = account.lock.refresh_token

    if refresh_token is not None and is_jwt_valid(refresh_token):
      logger.trace("logging in with refresh token")
      await client.login(
        username=account.login,
        refresh_token=refresh_token,
        identity_secret=account.identity_secret,
      )
    else:
      logger.trace("logging in with password")
      await client.login(
        username=account.login,
        password=account.password,
        shared_secret=account.shared_secret,
        identity_secret=account.identity_secret,
      )

    logger.trace("logged in (loop finished)")
    return True

  except Exception as e:
    logger.exception(f"Failed to login to Steam: {e}")
    return False
