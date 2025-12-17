from typing import List
from dataclasses import dataclass


@dataclass
class FreeProfileItem:
  app_id: int
  def_id: int
  name: str


FreeProfileItemsResponse = List[FreeProfileItem]
