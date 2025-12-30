from PyQt6.QtWidgets import QProgressBar

from ui.theme import CURRENT_THEME


class Progress(QProgressBar):
  def __init__(self, limit: int = 1, parent=None):
    super().__init__(parent)
    self.setTextVisible(False)
    self._setup_style()

    self.limit = limit
    self.value = 0

  def _setup_style(self):
    theme = CURRENT_THEME
    self.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {theme.BORDER};
                border-radius: 5px;
                background-color: {theme.INPUT_BACKGROUND};
                height: 12px;
                text-align: center; 
            }}
            
            QProgressBar::chunk {{
                background-color: {theme.ACCENT_GREEN};
                border-radius: 4px;
                margin: 1px;
            }}
        """)

  def inc(self, inc: int = 1):
    self.value += inc
    self.setValue(int(self.value / self.limit * 100))

  def set(self, val: int):
    self.value = val
    self.setValue(val)
