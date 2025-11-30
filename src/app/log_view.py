import html
import logging
from typing import List

from PyQt6.QtWidgets import QTextEdit, QComboBox, QLineEdit
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import QTimer

from ui.theme import CURRENT_THEME


class QtLogHandler(logging.Handler):
  def __init__(self, widget: "LogHandler"):
    super().__init__()
    self.widget = widget

  def emit(self, record):
    QTimer.singleShot(0, lambda: self.widget.append(record))


class LogHandler:
  def __init__(
    self,
    text_edit: QTextEdit,
    level_combo: QComboBox,
    filter_edit: QLineEdit,
  ):
    self.text_edit = text_edit
    self.level_combo = level_combo
    self.filter_edit = filter_edit

    self.buffer: List[logging.LogRecord] = []

    # TODO! configurable env
    private_build = False
    if private_build:
      fmt = "%(asctime)s [%(levelname)s]: %(message)s"
    else:
      fmt = "%(asctime)s %(message)s"

    self.text_edit.setReadOnly(True)
    self.formatter = logging.Formatter(fmt, "%H:%M:%S")

    self.level_combo.addItems(["DEBUG", "INFO", "WARN", "ERROR", "FATAL"])
    self.level_combo.setCurrentText("INFO")

    self.level_combo.currentTextChanged.connect(self.render)
    self.filter_edit.textChanged.connect(self.render)

  def _level_to_color(self, level: int) -> str:
    if level >= logging.ERROR:
      return CURRENT_THEME.LOG_ERROR
    if level >= logging.WARN:
      return CURRENT_THEME.LOG_WARN
    if level >= logging.INFO:
      return CURRENT_THEME.LOG_INFO
    return CURRENT_THEME.LOG_DEBUG

  def _format_record_as_html(self, record: logging.LogRecord) -> str:
    color = self._level_to_color(record.levelno)
    message = self.formatter.format(record)
    escaped_message = html.escape(message)
    return (
      f'<div style="font-family: Consolas, monospace; color: {color}; '
      f'word-wrap: break-word;">'
      f"{escaped_message}</div>"
    )

  def _scroll_to_top(self):
    scroll_bar = self.text_edit.verticalScrollBar()
    scroll_bar.setValue(scroll_bar.minimum())

  def append(self, record: logging.LogRecord):
    self.buffer.insert(0, record)

    if self._passes_filter(record):
      html_log = self._format_record_as_html(record)

      self.text_edit.moveCursor(QTextCursor.MoveOperation.Start)
      self.text_edit.insertHtml(html_log)
      self.render()

  def render(self):
    html_parts = [
      self._format_record_as_html(record)
      for record in self.buffer
      if self._passes_filter(record)
    ]

    self.text_edit.setHtml("".join(html_parts))
    # self._scroll_to_top()

  def clear(self):
    self.buffer.clear()
    self.text_edit.clear()

  def _get_current_min_level(self) -> int:
    level_map = {
      "DEBUG": logging.DEBUG,
      "INFO": logging.INFO,
      "WARN": logging.WARN,
      "ERROR": logging.ERROR,
      "FATAL": logging.FATAL,
    }
    return level_map.get(self.level_combo.currentText(), logging.INFO)

  def _passes_filter(self, record: logging.LogRecord) -> bool:
    if not record.name.startswith("yacs"):
      return False
    # record.name = record.name[len("yacs"):]

    if record.levelno < self._get_current_min_level():
      return False

    filter_text = self.filter_edit.text().strip()
    if filter_text and filter_text.lower() not in record.getMessage().lower():
      return False

    return True
