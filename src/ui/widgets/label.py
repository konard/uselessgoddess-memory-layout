from enum import Enum

from PyQt6.QtWidgets import QLabel

from ui.theme import CURRENT_THEME


class LabelType(Enum):
  PRIMARY = 1
  SECONDARY = 2
  HEADER = 3


class Label(QLabel):
  def __init__(
    self,
    text: str = "",
    label_type: LabelType = LabelType.PRIMARY,
    parent=None,
  ):
    super().__init__(text, parent)
    self._apply_style(label_type)

  def _apply_style(self, label_type: LabelType):
    theme = CURRENT_THEME

    color = theme.PRIMARY_TEXT
    font_weight = theme.FONT_WEIGHT_NORMAL
    font_size = theme.FONT_SIZE_NORMAL

    if label_type == LabelType.SECONDARY:
      color = theme.SECONDARY_TEXT
    elif label_type == LabelType.HEADER:
      font_weight = theme.FONT_WEIGHT_BOLD
      font_size = theme.FONT_SIZE_LARGE

    self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-family: "{theme.FONT_FAMILY}";
                font-size: {font_size}pt;
                font-weight: {font_weight};
                background-color: transparent;
                border: none;
            }}
        """)

  def set(self, text: str):
    super().setText(text)
