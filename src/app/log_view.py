from PyQt6.QtWidgets import QPlainTextEdit, QComboBox, QLineEdit

from typing import List, Tuple
import core.logging as logging

class LogHandler:
    def __init__(self, text_edit: QPlainTextEdit, level_combo: QComboBox, filter_edit: QLineEdit):
        self.text_edit = text_edit
        self.level_combo = level_combo
        self.filter_edit = filter_edit
        
        self.buffer: List[Tuple[int, str]] = [] 

        self.text_edit.setReadOnly(True)
        self.level_combo.addItems(["DEBUG", "INFO", "WARN", "ERROR", "FATAL"])
        self.level_combo.setCurrentText("INFO")

        self.level_combo.currentTextChanged.connect(self.render)
        self.filter_edit.textChanged.connect(self.render)

    def append(self, level: int, message: str):
        level_int = self._level_to_int(level) if isinstance(level, str) else level
        
        self.buffer.append((level_int, message))
        
        if self._passes_filter(level_int, message):
            self.text_edit.appendPlainText(message)

    def render(self):
        self.text_edit.clear()
        for level, message in self.buffer:
            if self._passes_filter(level, message):
                self.text_edit.appendPlainText(message)

    def clear(self):
        self.buffer.clear()
        self.text_edit.clear()

    def _level_to_int(self, level: str | int) -> int:
        if isinstance(level, int):
            return level
        
        mapping = {
            "TRACE": logging.TRACE,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARN": logging.WARN,
            "ERROR": logging.ERROR,
            "FATAL": logging.FATAL
        }             
        return mapping.get(level.upper(), logging.INFO)


    def _passes_filter(self, level_int: int, message: str) -> bool:
        min_level_str = self.level_combo.currentText()
        min_level_int = self._level_to_int(min_level_str)
        if level_int < min_level_int:
            return False
        
        filter_text = self.filter_edit.text().strip()
        if filter_text and filter_text.lower() not in message.lower():
            return False
            
        return True
