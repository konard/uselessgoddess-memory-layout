import time
import win32api
import win32con
import win32clipboard
import pywintypes
import pyautogui
from pyscreeze import ImageNotFoundException
import io


from core.account.model import RunningAccount
from constants import win_w, win_h
from core.logging import get_logger
from core.account import Account
from core.utils import async_methods
from PIL import Image

import resources

logger = get_logger("yacs.cs_controller")


def load_image(path: str) -> Image.Image:
  return Image.open(io.BytesIO(resources.load(path)))


class ZeroPosAccount:
  posX = 0
  posY = 0


@async_methods
class CS2Controller:
  def __init__(self):
    pass

  @staticmethod
  def move_mouse(x, y, account: Account):
    """Перемещает мышь"""
    logger.trace(f"Перемещает мышь: ({x}, {y})")
    abs_x = int(account.posX + x)
    abs_y = int(account.posY + y)
    try:
      win32api.SetCursorPos((abs_x, abs_y))
    except pywintypes.error as e:
      if e.winerror == 0:
        logger.debug(
          f"SetCursorPos failed with error 0, ignoring. Coords: ({abs_x}, {abs_y})"
        )
      else:
        raise
    logger.trace(f"Мышь перемещена: ({abs_x}, {abs_y})")

  @staticmethod
  def click(x, y, account: Account, immediate: bool = False):
    """Кликает в точку"""
    CS2Controller.move_mouse(x, y, account)
    time.sleep(0.2)
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
  def press_escape():
    """Нажимает кнопку Escape"""
    pyautogui.press("esc")
    time.sleep(0.1)
    logger.trace("Нажата кнопка Escape")

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
    print(x, y, account.posX, account.posY)
    try:
      matches = pyautogui.locateAllOnScreen(
        load_image(image), confidence=confidence
      )
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
          CS2Controller.click(click_x, click_y, ZeroPosAccount(), immediate)
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
      matches = pyautogui.locateAllOnScreen(
        load_image(image), confidence=confidence
      )
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

    x_max = account.posX + win_w
    y_max = account.posY + win_h

    x_min = account.posX
    y_min = account.posY

    while True:
      try:
        matches = pyautogui.locateAllOnScreen(load_image(image), confidence=0.9)
        for match in matches:
          if (
            match.left > x_min
            and match.left < x_max
            and match.top > y_min
            and match.top < y_max
          ):
            return True
      except ImageNotFoundException:
        pass

      if count > 250:
        raise Exception(f"Изображение не найдено: {image}")
      count += 1
      time.sleep(1)

  @staticmethod
  def click_bulk(image: str, account: RunningAccount, confidence: float = 0.9):
    """Кликает на все изображения"""

    x_max = account.posX + win_w
    y_max = account.posY + win_h

    x_min = account.posX
    y_min = account.posY

    matches = list(
      pyautogui.locateAllOnScreen(load_image(image), confidence=confidence)
    )
    for match in matches:
      if (
        match.left > x_min
        and match.left < x_max
        and match.top > y_min
        and match.top < y_max
      ):
        CS2Controller.click(
          (match.left + match.width / 2).astype("int"),
          (match.top + match.height / 2).astype("int"),
          ZeroPosAccount(),
          True,
        )
        time.sleep(0.5)

    return True

  @staticmethod
  def click_bulk_async(
    image: str, account: RunningAccount, confidence: float = 0.9
  ): ...

  @staticmethod
  async def move_mouse_async(x, y, account: Account): ...

  @staticmethod
  async def click_async(x, y, account: Account, immediate: bool = False): ...

  @staticmethod
  async def send_text_async(text: str): ...

  @staticmethod
  async def copy_to_clipboard_async(text: str): ...

  @staticmethod
  async def wait_async(secs: float): ...

  @staticmethod
  async def paste_from_clipboard_async(): ...

  @staticmethod
  async def select_all_async(): ...

  @staticmethod
  async def press_delete_async(): ...

  @staticmethod
  async def press_escape_async(): ...

  @staticmethod
  async def press_button_async(button: int, sleep: float = 0.1): ...

  @staticmethod
  async def click_if_exists_async(
    image: str,
    account: RunningAccount,
    confidence: float = 0.9,
    immediate: bool = False,
    whole_screen: bool = False,
  ) -> bool: ...

  @staticmethod
  async def check_if_exists_async(
    image: str, account: Account, confidence: float = 0.9
  ) -> bool: ...

  @staticmethod
  async def wait_for_image_async(image: str, account: Account): ...
