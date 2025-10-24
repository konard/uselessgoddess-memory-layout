from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from src.ui.align import Align


class VStack(QWidget):
  def __init__(
    self,
    *children: QWidget,
    align: Align = Align.Top,
    parent=None,
  ):
    super().__init__(parent)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    for child in children:
      layout.addWidget(child)

    layout.setAlignment(align.into_qt())
    if align == Align.Top:
      layout.addStretch()
