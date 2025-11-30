from typing import Callable, Optional
from PyQt6.QtWidgets import QPushButton
from ui.theme import CURRENT_THEME, ButtonType


class Button(QPushButton):
  def __init__(
    self,
    text: str,
    on_click: Optional[Callable[[bool], None]] = None,
    button_type: ButtonType = ButtonType.DEFAULT,
    tooltip: Optional[str] = None,
    parent=None,
  ):
    super().__init__(text, parent)

    if on_click:
      self.clicked.connect(on_click)

    if tooltip:
      self.setToolTip(tooltip)

    self._apply_style(button_type)

  def _apply_style(self, button_type: ButtonType):
    theme = CURRENT_THEME
    color_map = {
      ButtonType.SUCCESS: theme.ACCENT_GREEN,
      ButtonType.DANGER: theme.ACCENT_RED,
      ButtonType.PRIMARY: theme.ACCENT_BLUE,
      ButtonType.SPECIAL: theme.ACCENT_PURPLE,
      ButtonType.DEFAULT: theme.INPUT_BACKGROUND,
    }
    bg_color = color_map.get(button_type, theme.INPUT_BACKGROUND)

    self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {theme.PRIMARY_TEXT};
                border: none;
                padding: 8px 12px;
                border-radius: 5px;
                font-family: "{theme.FONT_FAMILY}";
                font-size: {theme.FONT_SIZE_NORMAL}pt;
                font-weight: {theme.FONT_WEIGHT_BOLD};
            }}
            QPushButton:hover {{
                background-color: {theme.BORDER};
            }}
            QPushButton:pressed {{
                background-color: {theme.BACKGROUND};
            }}
        """)
