from dataclasses import dataclass


@dataclass
class FreeProfileItem:
  app_id: int
  def_id: int
  name: str
  updated_at: str


FreeProfileItemsResponse = list[FreeProfileItem]
