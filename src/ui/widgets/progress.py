from PyQt6.QtWidgets import QProgressBar
from src.ui.theme import CURRENT_THEME


class Progress(QProgressBar):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setTextVisible(False)
    self._setup_style()

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
