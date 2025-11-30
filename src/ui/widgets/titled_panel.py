from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ui.theme import CURRENT_THEME


class TitledPanel(QWidget):
  def __init__(self, title: str, parent=None):
    super().__init__(parent)
    self.setObjectName("TitledPanel")

    self.setStyleSheet(f"""
            #TitledPanel {{
                background-color: {CURRENT_THEME.PANEL_BACKGROUND};
                border-radius: 8px;
            }}
        """)

    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(10, 10, 10, 10)
    main_layout.setSpacing(8)

    self.title_label = QLabel(title)
    self.title_label.setStyleSheet(f"""
            font-weight: bold;
            color: {CURRENT_THEME.PRIMARY_TEXT};
            padding-bottom: 5px;
            border-bottom: 1px solid {CURRENT_THEME.BORDER};
        """)

    self.container = QWidget()

    main_layout.addWidget(self.title_label)
    main_layout.addWidget(self.container)

    if not title:
      self.title_label.hide()
