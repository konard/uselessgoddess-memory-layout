from __future__ import annotations

import sys
from pathlib import Path
from typing import NoReturn

from PyQt6.QtWidgets import QApplication

from src.core.context import Context
from src.app.main_window import MainWindow


def main() -> NoReturn:
  app = QApplication(sys.argv)

  context = Context()
  window = MainWindow(context)
  window.show()

  sys.exit(app.exec())


if __name__ == "__main__":
  main()
