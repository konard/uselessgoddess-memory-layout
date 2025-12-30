from __future__ import annotations

from typing import Any

from core.logging import get_logger
from plugins import PluginBase

logger = get_logger("example_plugin")


class _ExamplePlugin(PluginBase):
  def __init__(self) -> None:
    self._context: dict[str, Any] | None = None

  def setup(self, app_context: dict[str, Any]) -> None:
    self._context = app_context
    logger.trace("Example plugin setup выполнен")
    event_bus = app_context.get("event_bus")
    if hasattr(event_bus, "subscribe"):
      event_bus.subscribe("task_progress", self._on_task_progress)

    # Добавим кнопку через публичный API окна — на левую панель
    gui_exec = app_context.get("gui_exec")
    window = app_context.get("window")
    if gui_exec and window and hasattr(window, "add_plugin_button"):

      def register_button() -> None:
        window.add_plugin_button("Плагин: Ping", self._on_ping)

      gui_exec.invoke(register_button)

  def teardown(self) -> None:
    logger.trace("Example plugin teardown выполнен")

  @property
  def meta(self) -> dict[str, Any]:
    return {"name": "Example Plugin", "version": "0.1.0"}

  def _on_task_progress(self, text: str) -> None:
    logger.debug("[example_plugin] task_progress: %s", text)

  def _on_ping(self) -> None:
    logger.trace("Plugin Ping!")


plugin = _ExamplePlugin()
