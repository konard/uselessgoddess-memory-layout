import time
import win32api
import win32con
import win32clipboard
import pyautogui
from pyscreeze import ImageNotFoundException

from core.account.model import RunningAccount
from src.constants import win_w, win_h
from core.logging import get_logger
from core.account import Account

logger = get_logger("yacs.cs_controller")


class CS2Controller:
  def __init__(self):
    pass

  @staticmethod
  def move_mouse(x, y, account: Account):
    """Перемещает мышь"""
    logger.trace(f"Перемещает мышь: ({x}, {y})")
    abs_x = account.posX + x
    abs_y = account.posY + y
    win32api.SetCursorPos((abs_x, abs_y))
    logger.trace(f"Мышь перемещена: ({abs_x}, {abs_y})")

  @staticmethod
  def click(x, y, account: Account, immediate: bool = False):
    """Кликает в точку"""
    CS2Controller.move_mouse(x, y, account)
    if not immediate:
      time.sleep(1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    logger.trace(f"Клик по ({x}, {y})")

  @staticmethod
  def send_text(text: str):
    """Вводит текст символ за символом"""
    for char in text:
      win32api.keybd_event(ord(char.upper()), 0, 0, 0)
      time.sleep(0.05)
      win32api.keybd_event(ord(char.upper()), 0, win32con.KEYEVENTF_KEYUP, 0)
    logger.trace(f"Текст введен: {text}")

  @staticmethod
  def copy_to_clipboard(text: str):
    """Копирует текст в буфер обмена"""
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text)
    win32clipboard.CloseClipboard()
    logger.trace(f"Текст скопирован в буфер: {text}")

  @staticmethod
  def wait(secs: float):
    """Ждет время"""
    logger.trace(f"Ждем {secs} секунд")
    time.sleep(secs)

  @staticmethod
  def paste_from_clipboard():
    """Вставляет текст из буфера Ctrl+V"""
    win32api.keybd_event(0x11, 0, 0, 0)  # Ctrl
    win32api.keybd_event(0x56, 0, 0, 0)  # V
    time.sleep(0.05)
    win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(0x11, 0, win32con.KEYEVENTF_KEYUP, 0)
    logger.trace("Вставка из буфера выполнена")

  @staticmethod
  def select_all():
    """Выделяет весь текст с помощью Ctrl+A"""
    win32api.keybd_event(0x11, 0, 0, 0)  # Ctrl
    win32api.keybd_event(0x41, 0, 0, 0)  # A
    time.sleep(0.05)
    win32api.keybd_event(0x41, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(0x11, 0, win32con.KEYEVENTF_KEYUP, 0)
    logger.trace("Выделение всего текста выполнено (Ctrl+A)")

  @staticmethod
  def press_delete():
    """Нажимает кнопку Delete"""
    win32api.keybd_event(win32con.VK_BACK, 0, 0, 0)
    time.sleep(0.1)
    win32api.keybd_event(win32con.VK_BACK, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)
    logger.trace("Нажата кнопка Delete")

  @staticmethod
  def press_button(button: int, sleep: float = 0.1):
    win32api.keybd_event(button, 0, 0, 0)
    time.sleep(sleep)
    win32api.keybd_event(button, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(sleep)
    logger.trace(f"Нажата кнопка: 0x{button:x}")

  @staticmethod
  def click_if_exists(
    image: str,
    account: RunningAccount,
    confidence: float = 0.9,
    immediate: bool = False,
    whole_screen: bool = False,
  ):
    """Кликает если изображение найдено"""
    x = account.posX + win_w
    y = account.posY + win_h

    try:
      matches = pyautogui.locateAllOnScreen(image, confidence=confidence)
      for match in matches:
        if (
          match[0] < x
          and match[1] < y
          and match[0] > account.posX
          and match[1] > account.posY
          or whole_screen
        ):
          click_x = int(match[0] + match[2] / 2)
          click_y = int(match[1] + match[3] / 2)
          CS2Controller.click(click_x, click_y, account, immediate)
          return True
      return False
    except ImageNotFoundException:
      logger.debug(
        f"Изображение не найдено: {image} (требуемая уверенность: {confidence})"
      )
      return False

  @staticmethod
  def check_if_exists(image: str, account: Account, confidence: float = 0.9):
    """Проверяет если изображение найдено"""
    x = account.posX + win_w
    y = account.posY + win_h

    try:
      matches = pyautogui.locateAllOnScreen(image, confidence=confidence)
      for match in matches:
        if (
          match[0] < x
          and match[1] < y
          and match[0] > account.posX
          and match[1] > account.posY
        ):
          return True
      return False
    except ImageNotFoundException:
      return False

  @staticmethod
  def wait_for_image(image: str, account: Account):
    """Ожидает появления изображения"""

    count = 0

    x = account.posX + win_w
    y = account.posY + win_h

    while True:
      try:
        matches = pyautogui.locateAllOnScreen(image, confidence=0.9)
        for match in matches:
          print(match)
          if (
            match[0] < x
            and match[1] < y
            and match[0] > account.posX
            and match[1] > account.posY
          ):
            return True
      except ImageNotFoundException:
        pass

      if count > 250:
        raise Exception(f"Изображение не найдено: {image}")
      count += 1
      print(count)
      time.sleep(1)
