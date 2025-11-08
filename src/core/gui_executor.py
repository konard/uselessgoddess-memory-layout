from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from core.logging import get_logger


logger = get_logger("GuiExecutor")


class GuiExecutor(QObject):
  """Выполняет произвольные коллбэки в GUI-потоке безопасно через сигнал."""

  _call_requested = pyqtSignal(object, tuple, dict)

  def __init__(self) -> None:
    super().__init__()
    self._call_requested.connect(self._on_call_requested)

  def invoke(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Запросить выполнение `func(*args, **kwargs)` в GUI-потоке."""
    self._call_requested.emit(func, args, kwargs)

  def _on_call_requested(
    self, func: Callable[..., Any], args: tuple, kwargs: dict
  ) -> None:  # type: ignore[override]
    try:
      func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
      logger.exception("Ошибка при выполнении GUI-коллбэка: %s", exc)
