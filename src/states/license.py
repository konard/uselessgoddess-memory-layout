import asyncio

from core.context import Context
from core.panel import State
from ui.widgets import Label, LabelType, VStack


class LicenseState(State):
  def __init__(self, next_state: State, reason_title: str, reason_desc: str):
    self.next_state = next_state
    self.title = reason_title
    self.desc = reason_desc

  def layout(self, ctx: Context, dispatch):
    return [
      VStack(
        Label(self.title, LabelType.HEADER),
        Label(self.desc, LabelType.SECONDARY),
        Label(
          "If this is caused by an unstable connection.\n"
          "Panel will automatically resume farming when network is fine.",
          LabelType.SECONDARY,
        ),
      )
    ]

  async def execute(self, ctx: Context):
    while not ctx.lic.is_working():
      await asyncio.sleep(1.0)
    return self.next_state
