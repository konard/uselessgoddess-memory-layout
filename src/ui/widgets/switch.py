from typing import Callable, Optional
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import (
  pyqtProperty,
  pyqtSignal,
  QEasingCurve,
  QPropertyAnimation,
  Qt,
)
from PyQt6.QtGui import QPainter, QColor

from src.ui.theme import CURRENT_THEME


class _SwitchSlider(QWidget):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setFixedSize(32, 16)

    self._handle_position = 3.0
    self._handle_off_pos = 3
    self._handle_on_pos = self.width() - self.height() + 3

    self.animation = QPropertyAnimation(self, b"handle_position", self)
    self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
    self.animation.setDuration(150)

  @pyqtProperty(float)
  def handle_position(self):
    return self._handle_position

  @handle_position.setter
  def handle_position(self, pos):
    self._handle_position = pos
    self.update()

  def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    track_color = QColor(
      CURRENT_THEME.ACCENT_GREEN
      if self._checked
      else CURRENT_THEME.INPUT_BACKGROUND
    )
    handle_color = QColor(CURRENT_THEME.PRIMARY_TEXT)

    painter.setBrush(track_color)
    painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)

    painter.setBrush(handle_color)
    painter.drawEllipse(int(self._handle_position), 3, 10, 10)

  def setChecked(self, checked):
    self._checked = checked
    self.animation.setStartValue(self.handle_position)
    self.animation.setEndValue(
      self._handle_on_pos if checked else self._handle_off_pos
    )
    self.animation.start()

  def isChecked(self):
    return self._checked


class Switch(QWidget):
  toggled = pyqtSignal(bool)

  def __init__(
    self,
    text: str = "",
    checked: bool = False,
    on_toggle: Optional[Callable[[], None]] = None,
    parent=None,
  ):
    super().__init__(parent)

    if on_toggle:
      self.toggled.connect(on_toggle)

    layout = QHBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)

    self._slider = _SwitchSlider()
    self._label = QLabel(text)
    self.setChecked(checked)

    layout.addWidget(self._slider)
    layout.addWidget(self._label)

  def mousePressEvent(self, event):
    event.accept()
    self.toggle()
    return super().mousePressEvent(event)

  def toggle(self):
    self.setChecked(not self.isChecked())

  def isChecked(self) -> bool:
    return self._slider.isChecked()

  def setChecked(self, checked: bool):
    self._slider.setChecked(checked)
    self.toggled.emit(checked)
