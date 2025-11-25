import math
from steam.ext.csgo.protobufs.cstrike import MatchmakingClientHello
from core.account.lock import AccountsLock
from core.account.model import FarmStatus
from core.services.gc.gc_parser import decode_bytes, decode_gc_bytes
from steam.ext.csgo.protobufs.econ import ClientRedeemFreeReward
from utils.is_in_wednesday_range import is_in_wednesday_range

from steam._const import READ_U32, CLEAR_PROTO_BIT
from core.logging import get_logger

logger = get_logger("player_info_service")


class PlayerInfoService:
  def __init__(self, lock: AccountsLock):
    self.lock = lock

  def process_message(self, data: bytes, login: str):
    decoded_message = decode_bytes(data)
    logger.trace("processing GC message for login: %s", login)
    if hasattr(decoded_message, "payload"):
      emsg_id = CLEAR_PROTO_BIT(READ_U32(decoded_message.payload))
      match emsg_id:
        case 4004:
          logger.trace("parsing player farm status for login: %s", login)
          try:
            self.parse_player_farm_status(decoded_message.payload, login)
          except Exception:
            logger.error(
              f"error parsing player farm status for login: {login}",
            )
        case 9110:
          logger.trace("parsing player stats: %s", login)
          try:
            self.parse_player_stats(decoded_message.payload, login)
          except Exception:
            logger.error(
              f"error parsing player stats for login: {login}",
            )
        case _:
          logger.trace("unknown emsg_id: %s", emsg_id)

  def parse_player_farm_status(self, data: bytes, login: str):
    msg = decode_gc_bytes(data)
    for i in msg.outofdate_subscribed_caches[0].objects:
      if i.type_id == 4:
        data = ClientRedeemFreeReward().parse(i.object_data[0])
        in_wd_range = is_in_wednesday_range(data.generation_time)
        neg = any(map(lambda x: x < 0, data.items))
        logger.trace("generation time: %s, neg: %s", data.generation_time, neg)
        if not neg and in_wd_range:
          self.lock.set_field(login, "status", FarmStatus.CAN_BE_LOOTED)
          return
        if neg and not in_wd_range:
          self.lock.set_field(login, "status", FarmStatus.NEED_TO_FARM)
          return
        self.lock.set_field(login, "status", FarmStatus.FARMED)
        return

  def parse_player_stats(self, data: bytes, login: str):
    msg: MatchmakingClientHello = decode_gc_bytes(data)
    self.lock.set_field(login, "lvl", msg.player_level)
    self.lock.set_field(login, "xp", max(msg.player_cur_xp - 327680000, 0))
