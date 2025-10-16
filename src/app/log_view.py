from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit


class LogView:
    """Инкапсулирует буфер и динамическую фильтрацию логов."""

    def __init__(self, txt_logs: QPlainTextEdit, cb_level: QComboBox, le_filter: QLineEdit) -> None:
        self._txt = txt_logs
        self._cb = cb_level
        self._le = le_filter
        self._buffer: List[Tuple[str, str]] = []

        self._cb.addItems(["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._cb.setCurrentText("INFO")
        self._cb.currentTextChanged.connect(self.render)
        self._le.textChanged.connect(self.render)

    def append(self, message: str, level: str) -> None:
        self._buffer.append((message, level))
        if self._passes(message, level):
            self._txt.appendPlainText(message)

    def clear(self) -> None:
        self._buffer.clear()
        self._txt.clear()

    def render(self) -> None:
        self._txt.setPlainText("")
        for message, level in self._buffer:
            if self._passes(message, level):
                self._txt.appendPlainText(message)

    # --- helpers ---
    @staticmethod
    def _level_to_int(level: str) -> int:
        mapping = {"TRACE": 5, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        return mapping.get(level.upper(), 100)

    def _passes(self, message: str, level: str) -> bool:
        level_filter = self._cb.currentText()
        if self._level_to_int(level) < self._level_to_int(level_filter):
            return False
        text = self._le.text().strip()
        if text and text.lower() not in message.lower():
            return False
        return True


