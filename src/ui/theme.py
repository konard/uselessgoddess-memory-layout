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
  FONT_WEIGHT_NORMAL: str = "normal"
  FONT_WEIGHT_BOLD: str = "bold"

  LOG_DEBUG: str = ACCENT_BLUE
  LOG_INFO: str = PRIMARY_TEXT
  LOG_WARN: str = ACCENT_YELLOW
  LOG_ERROR: str = ACCENT_RED


class ButtonType(Enum):
  DEFAULT = auto()
  SUCCESS = auto()
  DANGER = auto()
  PRIMARY = auto()
  SPECIAL = auto()


CURRENT_THEME = Theme()
