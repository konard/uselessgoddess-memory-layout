from typing import Set, List
from PyQt6.QtCore import QObject, pyqtSignal
from core.logging import get_logger

logger = get_logger("sv.ui")


class UIService(QObject):
  selection_changed = pyqtSignal()

  def __init__(self):
    super().__init__()
    self._selected: Set[str] = set()

  def select(self, login: str):
    if login not in self._selected:
      self._selected.add(login)
      self.selection_changed.emit()
      logger.trace(f"UI selected: {login}")

  def deselect(self, login: str):
    if login in self._selected:
      self._selected.remove(login)
      self.selection_changed.emit()
      logger.trace(f"UI deselected: {login}")

  def toggle(self, login: str, state: bool):
    if state:
      self.select(login)
    else:
      self.deselect(login)

  def clear_selection(self):
    self._selected.clear()
    self.selection_changed.emit()

  def set_selection(self, logins: List[str]):
    self._selected = set(logins)
    self.selection_changed.emit()

  @property
  def selected_logins(self) -> List[str]:
    return list(self._selected)

  def capture_selected(self) -> List[str]:
    res = list(self._selected)
    self.clear_selection()
    return res
