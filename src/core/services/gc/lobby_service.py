from __future__ import annotations

from typing import Tuple, TYPE_CHECKING
import asyncio
import time

import struct
import vdf
from steam.protobufs.clientserver_mms import CMsgClientMMSLobbyData
from steam.protobufs.client_server_2 import CMsgClientOfflineMessageNotification

if TYPE_CHECKING:
  from core.context import Context

from core.services.gc.gc_parser import decode_bytes
from steam.protobufs.client_server import CMsgClientChatInvite
from core.account import Account
from core.logging import get_logger
from core.services.gc.match_warning import MatchWarning

logger = get_logger("lobby_service")

# Время жизни инвайта в секундах (1 минута)
INVITE_EXPIRATION_TIME = 10

# Таймаут ожидания инвайта в секундах (2 минуты)
INVITE_WAIT_TIMEOUT = 30


class InviteExpiredError(Exception):
  """Исключение, выбрасываемое когда инвайт просрочен"""

  pass


class InviteTimeoutError(Exception):
  """Исключение, выбрасываемое когда инвайт не получен в течение таймаута"""

  pass


class LobbyService:
  match_warning: MatchWarning = MatchWarning()
  ctx: Context

  def __init__(self, ctx: Context):
    self.ctx = ctx
    self.invites: dict[
      str, Tuple[CMsgClientChatInvite | None, asyncio.Event, float | None]
    ] = {}

  async def wait_for_invite(self, account: Account) -> CMsgClientChatInvite:
    """
    Ожидает получения инвайта для конкретного аккаунта.

    Args:
        account: Аккаунт, для которого ожидается инвайт

    Returns:
        CMsgClientChatInvite: Объект инвайта

    Raises:
        InviteExpiredError: Если инвайт просрочен
        InviteTimeoutError: Если инвайт не получен в течение таймаута
    """
    steam_id = str(account.steam_id)

    # Создаем event если его еще нет
    if steam_id not in self.invites:
      new_event = asyncio.Event()
      self.invites[steam_id] = (None, new_event, None)

    # Получаем event для ожидания
    _, event, _ = self.invites[steam_id]

    # Ждем получения инвайта с таймаутом
    try:
      await asyncio.wait_for(event.wait(), timeout=INVITE_WAIT_TIMEOUT)
    except asyncio.TimeoutError:
      # Удаляем запись при таймауте
      if steam_id in self.invites:
        del self.invites[steam_id]
      raise InviteTimeoutError(
        f"Invite timeout for steam_id {steam_id}. Waited {INVITE_WAIT_TIMEOUT}s"
      )

    # После того как event зарезолвился, читаем актуальные данные из словаря
    # (они могли измениться пока мы ждали)
    if steam_id not in self.invites:
      raise ValueError(
        f"Invite entry was removed while waiting for steam_id {steam_id}"
      )

    invite, _, received_at = self.invites[steam_id]

    # Очищаем event для следующего использования
    event.clear()

    if invite is None:
      # Удаляем запись если инвайт None
      if steam_id in self.invites:
        del self.invites[steam_id]
      raise ValueError(
        f"Invite event was set but invite data is None for steam_id {steam_id}"
      )

    # Проверяем, не просрочен ли инвайт
    if received_at is not None:
      elapsed_time = time.time() - received_at
      if elapsed_time > INVITE_EXPIRATION_TIME:
        del self.invites[steam_id]
        raise InviteExpiredError(
          f"Invite expired for steam_id {steam_id}. "
          f"Elapsed time: {elapsed_time:.2f}s, max: {INVITE_EXPIRATION_TIME}s"
        )

    return invite

  def set_invite(self, steam_id: str, invite: CMsgClientChatInvite):
    """
    Устанавливает инвайт для steam_id и пробуждает ожидающий код.

    Args:
        steam_id: Steam ID пользователя, для которого получен инвайт
        invite: Объект инвайта
    """
    steam_id_str = str(steam_id)
    received_at = time.time()

    if steam_id_str in self.invites:
      _, event, _ = self.invites[steam_id_str]
      self.invites[steam_id_str] = (invite, event, received_at)
      event.set()
    else:
      event = asyncio.Event()
      event.set()
      self.invites[steam_id_str] = (invite, event, received_at)

    logger.trace(
      f"Invite set for steam_id: {steam_id_str} at {received_at:.2f}"
    )
    return True

  def process_chat_invite(self, data: bytes):
    decoded_message: CMsgClientChatInvite = decode_bytes(data)
    steam_id_invited = str(decoded_message.steam_id_invited)
    self.set_invite(steam_id_invited, decoded_message)

  def process_match_warning(self, data: bytes, login: str):
    emsg = struct.unpack("<I", data[:4])[0]
    if emsg & 0x80000000:
      header_len = struct.unpack("<I", data[4:8])[0]
      body = data[8 + header_len :]
    else:
      body = data[4:]  # Fallback for non-proto (should not happen for 6612)

    MMSLobbyData = CMsgClientMMSLobbyData().parse(body)
    metadata = list(vdf.binary_loads(MMSLobbyData.metadata).values())[0]
    self.match_warning.process_message(metadata, login)

  def process_offline_event(self, data: bytes, login: str):
    decoded_message: CMsgClientOfflineMessageNotification = decode_bytes(data)
    print(decoded_message)

  def process_message(self, data: bytes, login: str, msg_id: int):
    """Обрабатывает входящие сообщения и ищет инвайты"""
    if msg_id == 800:
      logger.trace(f"Received chat invite for {login}")
      self.process_chat_invite(data)
    elif msg_id == 6612:
      self.process_match_warning(data, login)
    elif msg_id == 7523:
      self.process_offline_event(data, login)
    else:
      pass
