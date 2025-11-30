from dataclasses import dataclass
from enum import Enum, auto


@dataclass
class Theme:
  BACKGROUND: str = "#282828"
  PANEL_BACKGROUND: str = "#3c3836"
  PRIMARY_TEXT: str = "#ebdbb2"
  SECONDARY_TEXT: str = "#a89984"

  ACCENT_GREEN: str = "#98971a"
  ACCENT_YELLOW: str = "#cc241d"
  ACCENT_ORANGE: str = "#fe8019"
  ACCENT_RED: str = "#cc241d"
  ACCENT_BLUE: str = "#458588"
  ACCENT_PURPLE: str = "#b16286"

  BORDER: str = "#504945"
  INPUT_BACKGROUND: str = "#504945"

  FONT_FAMILY: str = "Segoe UI"
  FONT_SIZE_NORMAL: int = 10
  FONT_SIZE_LARGE: int = 14
  FONT_WEIGHT_NORMAL: str = "normal"
  FONT_WEIGHT_BOLD: str = "bold"

  LOG_DEBUG: str = ACCENT_BLUE
  LOG_INFO: str = PRIMARY_TEXT
  LOG_WARN: str = ACCENT_ORANGE
  LOG_ERROR: str = ACCENT_RED


class ButtonType(Enum):
  DEFAULT = auto()
  SUCCESS = auto()
  DANGER = auto()
  PRIMARY = auto()
  SPECIAL = auto()


CURRENT_THEME = Theme()

MAIN_WINDOW_STYLESHEET = f"""
  QWidget {{ 
      background-color: {CURRENT_THEME.BACKGROUND}; 
      color: {CURRENT_THEME.PRIMARY_TEXT}; 
  }}
  QTabWidget::pane {{ 
      border: none; 
  }}
  QTabBar::tab {{ 
      background: {CURRENT_THEME.PANEL_BACKGROUND}; 
      color: {CURRENT_THEME.SECONDARY_TEXT}; 
      padding: 8px 20px; 
      margin-right: 2px; 
  }}
  QTabBar::tab:selected {{ 
      background: {CURRENT_THEME.INPUT_BACKGROUND}; 
      color: {CURRENT_THEME.PRIMARY_TEXT}; 
      border-bottom: 2px solid {CURRENT_THEME.ACCENT_BLUE}; 
  }}
"""
