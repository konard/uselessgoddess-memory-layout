#!/usr/bin/env python3
"""
Скрипт для отображения координат мыши в реальном времени в консоли.
Нажмите Ctrl+C для выхода.
"""

import sys

from pynput import mouse


def on_move(x, y):
  """Обработчик движения мыши"""
  print(f"\rКоординаты: X={x:6.0f}, Y={y:6.0f}", end="", flush=True)


def on_click(x, y, button, pressed):
  """Обработчик клика мыши"""
  if pressed:
    button_name = (
      "ЛКМ"
      if button == mouse.Button.left
      else "ПКМ"
      if button == mouse.Button.right
      else "СКМ"
    )
    print(f"\nКлик {button_name} на координатах: X={x:6.0f}, Y={y:6.0f}")


def main():
  print("Отслеживание координат мыши запущено. Нажмите Ctrl+C для выхода.")
  print("Координаты обновляются в реальном времени...\n")

  try:
    # Создаем слушатель мыши
    with mouse.Listener(on_move=on_move, on_click=on_click) as listener:
      listener.join()
  except KeyboardInterrupt:
    print("\n\nОтслеживание остановлено.")
    sys.exit(0)


if __name__ == "__main__":
  main()
