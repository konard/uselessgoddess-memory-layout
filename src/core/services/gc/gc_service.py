from typing import TYPE_CHECKING, List, Set
from core.account.model import Account
from core.services.gc.lobby_service import LobbyService
from core.services.gc.player_info_service import PlayerInfoService
from core.services.gc.event_service import EventService
from core.logging import get_logger

if TYPE_CHECKING:
  from core.context import Context
  from core.panel import StateManager

logger = get_logger("sv.gc")


class GCService:
  ctx: "Context"
  manager: "StateManager"
  player_info_service: PlayerInfoService
  lobby_service: LobbyService

  connected_accounts: Set[str]

  def __init__(self, ctx: "Context"):
    self.ctx = ctx
    self.player_info_service = PlayerInfoService(ctx)
    self.lobby_service = LobbyService(ctx)
    self.event_service = EventService()
    self.connected_accounts = set()

  def all_connected(self, accounts: List[Account]) -> bool:
    return all(account.login in self.connected_accounts for account in accounts)

  def process_message(self, data: bytes, msg_id: int, login: str):
    # logger.trace(f"<recv> raw msg_id: {msg_id} -> {login}")

    if login not in self.connected_accounts:
      self.connected_accounts.add(login)
      return

    if msg_id == 5453:
      self.player_info_service.process_message(data, login)

    if msg_id in [800, 6612, 6604, 7523]:
      self.lobby_service.process_message(data, login, msg_id)
