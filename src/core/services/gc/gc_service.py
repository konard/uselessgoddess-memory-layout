from core.services.gc.lobby_service import LobbyService
from core.services.gc.matcher_service import MatcherService
from core.services.gc.player_info_service import PlayerInfoService
from core.account.lock import AccountsLock


class GCService:
  player_info_service: PlayerInfoService = PlayerInfoService(AccountsLock())
  lobby_service: LobbyService = LobbyService()
