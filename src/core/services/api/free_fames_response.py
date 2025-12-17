from typing import List


class FreeGame:
  pkg_id: int
  app_id: int
  name: str
  updated_at: str


FreeGamesResponse = List[FreeGame]
