import asyncio

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from app.srt_table import SRTTable
from core.context import Context
from core.logging import get_logger
from core.utils import run_blocking
from ui import ButtonType
from ui.widgets import Button, TitledPanel

logger = get_logger("ui.srt")


class SRTTab(QWidget):
  def __init__(self, ctx: Context, parent=None):
    super().__init__(parent)
    self.ctx = ctx
    self._setup_ui()

    asyncio.create_task(self._init_srt())

  def _setup_ui(self):
    layout = QHBoxLayout(self)
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(5)

    self.srt_panel = TitledPanel("")
    panel_layout = QVBoxLayout(self.srt_panel.container)
    panel_layout.setContentsMargins(0, 0, 0, 0)

    self.srt_table = SRTTable(on_toggle_block=self._on_srt_block_toggle)
    panel_layout.addWidget(self.srt_table)

    btn_layout = QHBoxLayout()
    btn_layout.addWidget(
      Button(
        "Ping",
        on_click=lambda _: asyncio.create_task(self._refresh_srt_ping()),
        button_type=ButtonType.PRIMARY,
      )
    )
    btn_layout.addWidget(
      Button(
        "Block All",
        on_click=self._block_all_srt_rules,
        button_type=ButtonType.DANGER,
      )
    )
    btn_layout.addWidget(
      Button(
        "Clear Rules",
        on_click=self._clear_srt_rules,
        button_type=ButtonType.DANGER,
      )
    )
    panel_layout.addLayout(btn_layout)

    layout.addWidget(self.srt_panel)
    layout.addStretch()

  async def _init_srt(self):
    logger.debug("loading SRT config...")
    try:
      routes = await run_blocking(self.ctx.srt.load_routes)
      self.srt_table.populate(routes)
      await self._refresh_srt_ping()
    except Exception as e:
      logger.error(f"Failed to init SRT: {e}")

  async def _refresh_srt_ping(self, _=None):
    await self.ctx.srt.ping_all()
    self.srt_table.populate(self.ctx.srt.routes)

  def _on_srt_block_toggle(self, route_name: str, checked: bool):
    self.ctx.srt.toggle_route(route_name, checked)

  def _clear_srt_rules(self, _=None):
    self.ctx.srt.clear_all_rules()
    self.srt_table.populate(self.ctx.srt.routes)

  def _block_all_srt_rules(self, _=None):
    self.ctx.srt.block_all_routes()
    self.srt_table.populate(self.ctx.srt.routes)
