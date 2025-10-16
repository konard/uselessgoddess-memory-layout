from __future__ import annotations

import logging
from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal
import logging


class QtLogEmitter(QObject):
    new_log = pyqtSignal(str, str)  # message, level


class GuiLogHandler(logging.Handler):
    """Лог-хендлер, пересылающий записи в GUI через сигнал."""

    def __init__(self, emitter: QtLogEmitter) -> None:
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            msg = self.format(record)
            self.emitter.new_log.emit(msg, record.levelname)
        except Exception:
            # не бросаем исключения из обработчика логов
            pass


def install_gui_log_handler(append_fn: Callable[[str, str], None]) -> GuiLogHandler:
    """Устанавливает GUI-хэндлер в корневой логгер и возвращает его.

    append_fn: функция-приёмник вида (message, level) — обычно window.append_log.
    """
    emitter = QtLogEmitter()
    emitter.new_log.connect(append_fn)
    handler = GuiLogHandler(emitter)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logging.getLogger().addHandler(handler)
    return handler


