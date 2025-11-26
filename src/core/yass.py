import time
from typing import List

from core.account.model import RunningAccount
from core.services.cs_controller import CS2Controller
from core.services.windows_service import WindowService
from core.utils import async_methods
from core.logging import get_logger

logger = get_logger("yass")


@async_methods
class Yass:
  @staticmethod
  def press_resource(resource: str, accounts: List[RunningAccount]):
    try:
      CS2Controller.move_mouse(4, 4, accounts[0])
      side_a_button = CS2Controller.check_if_exists(resource, accounts[0], 0.8)
      side_b_button = CS2Controller.check_if_exists(resource, accounts[1], 0.8)
      count = 5

      while side_a_button or side_b_button or count > 0:
        side_a_button = CS2Controller.check_if_exists(
          resource, accounts[0], 0.8
        )
        side_b_button = CS2Controller.check_if_exists(
          resource, accounts[1], 0.8
        )
        if side_a_button:
          WindowService.focus_window(accounts[0].win_cs_title)
          CS2Controller.click_if_exists(resource, accounts[0], 0.8, True)
          time.sleep(0.5)
          CS2Controller.move_mouse(3, 3, accounts[0])
        if side_b_button:
          WindowService.focus_window(accounts[1].win_cs_title)
          CS2Controller.click_if_exists(resource, accounts[1], 0.8, True)
          time.sleep(0.5)
          CS2Controller.move_mouse(3, 3, accounts[1])
        if not (side_a_button or side_b_button):
          count -= 1
      else:
        count = 5

    except Exception as e:
      logger.error(f"Press button error: {e}")

  @staticmethod
  async def press_resource_async(
    resource: str, accounts: List[RunningAccount]
  ): ...
