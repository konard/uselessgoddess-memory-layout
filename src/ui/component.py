import enum

from PyQt6.QtWidgets import QWidget


class Style(enum.Enum):
  Default = (0,)
  Primary = (1,)
  Danger = (2,)


class Align(enum.Enum):
  Center = (0,)
  Top = (1,)
  Bottom = (2,)
  Left = (3,)
  Right = (4,)


class Component:
  def into_widget(self) -> QWidget:
    """
    Returns the underlying Qt widget for rendering.
    This is the bridge between the abstraction and the concrete implementation.
    """
    raise NotImplementedError("missing .into_widget() implementation")
