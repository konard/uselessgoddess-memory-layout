from typing import Callable, Optional
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QPushButton

from .component import Component, Style


STYLES = {
  Style.Default: """
        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #c0c0c0;
            padding: 5px 10px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
        }
        QPushButton:pressed {
            background-color: #d0d0d0;
        }
    """,
  Style.Primary: """
        QPushButton {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #0069d9;
        }
        QPushButton:pressed {
            background-color: #005cbf;
        }
    """,
  Style.Danger: """
        QPushButton {
            background-color: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #c82333;
        }
        QPushButton:pressed {
            background-color: #bd2130;
        }
    """,
}


class Button(Component):
  def __init__(
    self,
    text: str,
    *,
    on_click: Optional[Callable[[], None]] = None,
    icon_path: Optional[str] = None,
    tooltip: Optional[str] = None,
    style_name: str = "default",
    parent=None,
  ):
    self._widget = QPushButton(text)

    if on_click:
      self._widget.clicked.connect(on_click)

    if icon_path:
      self._widget.setIcon(QIcon(icon_path))
      self._widget.setIconSize(QSize(16, 16))

    if tooltip:
      self._widget.setToolTip(tooltip)

    self._widget.setStyleSheet(STYLES.get(style_name, STYLES[Style.Default]))

  def into_widget(self) -> QPushButton:
    return self._widget
