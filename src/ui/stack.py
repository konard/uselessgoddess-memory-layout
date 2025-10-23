from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from .component import Component, Align

class VStack(Component):
  def __init__(self, *children: Component, align: Align = Align.Center):
    self._widget = QWidget()
    layout = QVBoxLayout(self._widget)
    layout.setContentsMargins(0, 0, 0, 0)

    for child in children:
      layout.addWidget(child.into_widget())

    if align == Align.Center:
      layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    elif align == Align.Top:
      layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    elif align == Align.Bottom:
      layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
    elif align == Align.Left:
      layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    elif align == Align.Right:
      layout.setAlignment(Qt.AlignmentFlag.AlignRight)

    if align in (Align.Center, Align.Top, Align.Bottom):
      layout.addStretch()

  def into_widget(self) -> QWidget:
    return self._widget
