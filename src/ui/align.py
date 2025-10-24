from enum import Enum, auto
from PyQt6.QtCore import Qt


class Align(Enum):
  Top = auto()
  Center = auto()
  Bottom = auto()

  def into_qt(self) -> Qt.AlignmentFlag:
    return _alignment_map[self]


_alignment_map = {
  Align.Top: Qt.AlignmentFlag.AlignTop,
  Align.Center: Qt.AlignmentFlag.AlignCenter,
  Align.Bottom: Qt.AlignmentFlag.AlignBottom,
}
