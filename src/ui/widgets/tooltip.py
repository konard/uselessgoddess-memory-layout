from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QLabel

from ui.theme import CURRENT_THEME


class Tooltip(QLabel):
  def __init__(self, parent=None):
    super().__init__(parent)

    self.setWindowFlags(Qt.WindowType.ToolTip)

    self.setStyleSheet(f"""
            QLabel {{
                background-color: {CURRENT_THEME.PANEL_BACKGROUND};
                color: {CURRENT_THEME.PRIMARY_TEXT};
                border: 1px solid {CURRENT_THEME.BORDER};
                padding: 6px;
                border-radius: 4px;
                /* Используем шрифт из темы */
                font-family: "{CURRENT_THEME.FONT_FAMILY}";
                font-size: {CURRENT_THEME.FONT_SIZE_NORMAL}pt;
            }}
        """)

  def show_tip(self, pos: QPoint, text: str):
    if not text:
      self.hide()
      return

    self.setText(text)
    self.adjustSize()

    self.move(pos.x() + 15, pos.y() + 10)
    self.show()

  def hide_tip(self):
    self.hide()
