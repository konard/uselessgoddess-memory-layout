from typing import TYPE_CHECKING
from core.services.gc.lobby_service import LobbyService
from core.services.gc.matcher_service import MatcherService
from core.services.gc.player_info_service import PlayerInfoService
from core.account.lock import AccountsLock


if TYPE_CHECKING:
  from core.context import Context
  from core.panel import StateManager


class GCService:
  ctx: "Context"
  manager: "StateManager"
  player_info_service: PlayerInfoService
  lobby_service: LobbyService

  def __init__(self, ctx: "Context"):
    self.ctx = ctx
    self.player_info_service = PlayerInfoService(AccountsLock())
    self.lobby_service = LobbyService(ctx)

  def process_message(self, data: bytes, msg_id: int, login: str):
    if msg_id == 5453:
      self.player_info_service.process_message(data, login)

    if msg_id in [800, 6612, 7523]:
      self.lobby_service.process_message(data, login, msg_id)
