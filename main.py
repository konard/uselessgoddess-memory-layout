from __future__ import annotations

import sys
import asyncio
import qasync

from PyQt6.QtWidgets import QApplication

from src.core.context import Context
from src.app.main_window import MainWindow
from src.states import Idle

async def main():
  _app = QApplication.instance() or QApplication(sys.argv)
    
  context = Context()

  window = MainWindow(context)
  window.show()
  
  await window.manager.into_state(Idle())

  await asyncio.get_event_loop().create_future()
  


if __name__ == "__main__":
    try:
        qasync.run(main())
    except asyncio.CancelledError:
        pass
