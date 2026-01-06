import math
import traceback
from typing import TYPE_CHECKING

from steam._const import CLEAR_PROTO_BIT, READ_U32
from steam.ext.csgo.protobufs.cstrike import MatchmakingClientHello
from steam.ext.csgo.protobufs.econ import ClientRedeemFreeReward

from core.logging import get_logger
from core.services.gc.gc_parser import decode_bytes, decode_gc_bytes
from core.services.gc.matcher_service import MatcherService
from utils.is_in_wednesday_range import is_in_wednesday_range

if TYPE_CHECKING:
  from core.context import Context

logger = get_logger("player_info_service")


class PlayerInfoService:
  ctx: "Context"
  matcher_service: MatcherService = MatcherService()

  def __init__(self, ctx: "Context"):
    self.ctx = ctx

  def process_message(self, data: bytes, login: str):
    decoded_message = decode_bytes(data)
    logger.trace("processing GC message for login: %s", login)
    if hasattr(decoded_message, "payload"):
      emsg_id = CLEAR_PROTO_BIT(READ_U32(decoded_message.payload))
      match emsg_id:
        case 9110:
          logger.trace("parsing player stats: %s", login)
          try:
            self.parse_player_stats(decoded_message.payload, login)
          except Exception:
            logger.trace(
              f"ERROR: parsing player stats for login: {login}",
            )
        case 9107:
          logger.trace("parsing player match id: %s", login)
          try:
            self.matcher_service.process_message(decoded_message.payload, login)
          except Exception as e:
            logger.error(
              f"error parsing player match id for login: {login}: {e}",
            )
            print(traceback.format_exc())
        case _:
          logger.trace("unknown emsg_id: %s", emsg_id)

  def parse_player_farm_status(self, data: bytes, login: str):
    msg = decode_gc_bytes(data)
    for i in msg.outofdate_subscribed_caches[0].objects:
      if i.type_id == 4:
        data = ClientRedeemFreeReward().parse(i.object_data[0])
        in_wd_range = is_in_wednesday_range(data.generation_time)
        neg = any(x < 0 for x in data.items)
        logger.trace("generation time: %s, neg: %s", data.generation_time, neg)
        print(in_wd_range)
        return

  def parse_player_stats(self, data: bytes, login: str):
    msg: MatchmakingClientHello = decode_gc_bytes(data)
    self.ctx.account.accounts[login].lock.lvl = msg.player_level
    self.ctx.account.accounts[login].lock.xp = max(msg.player_cur_xp - 327680000, 0)
