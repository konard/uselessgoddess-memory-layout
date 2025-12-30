from __future__ import annotations

import asyncio

from core.account import Account
from core.logging import get_logger

logger = get_logger("sv.match_warning")


class MatchWarning:
  states: dict[str, str] = {}
  events: dict[str, asyncio.Event] = {}

  def process_message(self, data: dict, login: str):
    queue_state = data.get("game:mmqueue")
    if not queue_state:
      return

    logger.trace(f"Got mmqueue state '{queue_state}' for {login}")
    self.states[login] = queue_state

    if login in self.events:
      self.events[login].set()
    else:
      event = asyncio.Event()
      event.set()
      self.events[login] = event

  def is_searching(self, account: Account) -> bool:
    if account.login in self.states:
      return self.states[account.login] == "searching"
    return False

  def is_registering(self, account: Account) -> bool:
    if account.login in self.states:
      return self.states[account.login] == "registering"
    return False

  async def wait_for_searching(self, accounts: list[Account]) -> bool:
    self.states.clear()
    for acc in accounts:
      if acc.login in self.events:
        self.events[acc.login].clear()
      else:
        self.events[acc.login] = asyncio.Event()

    pending_logins = {acc.login for acc in accounts}
    # Таймаут ожидания перехода в searching (30 секунд)
    timeout = 30.0
    start_time = asyncio.get_event_loop().time()

    try:
      while pending_logins:
        current_time = asyncio.get_event_loop().time()
        if current_time - start_time > timeout:
          logger.error("Timeout waiting for searching state")
          # Проверяем последние состояния
          for login in pending_logins:
            last_state = self.states.get(login)
            logger.warn(f"Account {login} timed out with state: {last_state}")
            if last_state == "registering":
              # По условию: если последнее сообщение registering - false
              return False
          return False

        # Ждем обновлений для всех ожидающих аккаунтов
        wait_tasks = [
          asyncio.create_task(self.events[login].wait(), name=login)
          for login in pending_logins
        ]

        # Ждем хотя бы одного обновления
        # Используем небольшой таймаут для проверки общего времени
        done, _ = await asyncio.wait(
          wait_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=1.0
        )

        if not done:
          # Никто не обновился за 1 секунду, проверяем общий таймаут в следующей итерации
          for task in wait_tasks:
            task.cancel()
          continue

        for task in done:
          login = task.get_name()
          self.events[login].clear()  # Сбрасываем событие для следующего обновления

          current_state = self.states.get(login)

          if current_state == "searching":
            if login in pending_logins:
              logger.info(f"{login} is searching")
              pending_logins.remove(login)

          elif current_state == "registering":
            # Просто продолжаем ждать
            logger.trace(f"{login} is registering...")

          # Можно добавить обработку других статусов если нужно

        # Отменяем остальные задачи ожидания в этом цикле
        for task in wait_tasks:
          if not task.done():
            task.cancel()

      logger.info("All accounts are searching")
      return True

    except Exception as e:
      logger.error(f"Failed to wait for searching: {e}")
      return False
