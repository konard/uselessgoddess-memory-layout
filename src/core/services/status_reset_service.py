import asyncio
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from core.account.lock import AccountsLock
from core.account.model import FarmStatus
from core.logging import get_logger

logger = get_logger("sv.status_reset")

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

RESET_DAY = 2  # 0 = понедельник, 2 = среда
RESET_HOUR = 5
RESET_MINUTE = 0

LAST_RESET_KEY = "__last_status_reset_date__"


class StatusResetService:
  """Сервис для автоматического сброса статусов аккаунтов каждую среду в 5:00 МСК."""

  def __init__(self):
    self.account_lock = AccountsLock()
    self._last_reset_date: date | None = self._load_last_reset_date()
    self._running = False

  def _load_last_reset_date(self) -> date | None:
    """Загрузить дату последнего сброса из базы данных."""
    try:
      last_reset_str = self.account_lock.get_field(LAST_RESET_KEY, "last_reset_date")
      if last_reset_str:
        return datetime.fromisoformat(last_reset_str).date()
    except Exception as e:
      logger.debug(f"Could not load last reset date: {e}")
    return None

  def _save_last_reset_date(self, reset_date: date):
    """Сохранить дату последнего сброса в базу данных."""
    try:
      self.account_lock.set_field(
        LAST_RESET_KEY, "last_reset_date", reset_date.isoformat()
      )
      self._last_reset_date = reset_date
    except Exception as e:
      logger.error(f"Failed to save last reset date: {e}")

  def _get_last_wednesday_5am(self, now: datetime) -> datetime:
    """Получить дату и время последней среды в 5:00."""
    days_since_monday = now.weekday()
    if days_since_monday < RESET_DAY:
      days_back = days_since_monday + (7 - RESET_DAY)
    elif days_since_monday == RESET_DAY:
      if now.hour < RESET_HOUR or (now.hour == RESET_HOUR and now.minute < RESET_MINUTE):
        days_back = 7
      else:
        days_back = 0
    else:
      days_back = days_since_monday - RESET_DAY

    last_wednesday = now - timedelta(days=days_back)
    return last_wednesday.replace(
      hour=RESET_HOUR, minute=RESET_MINUTE, second=0, microsecond=0
    )

  async def start(self):
    """Запустить фоновую задачу проверки времени."""
    if self._running:
      logger.warning("StatusResetService already running")
      return

    self._running = True
    logger.info("StatusResetService started")

    self._check_and_reset_on_startup()

    asyncio.create_task(self._check_loop())

  def _check_and_reset_on_startup(self):
    now_moscow = datetime.now(MOSCOW_TZ)
    last_wednesday_5am = self._get_last_wednesday_5am(now_moscow)
    last_wednesday_date = last_wednesday_5am.date()

    if self._last_reset_date is None or self._last_reset_date < last_wednesday_date:
      logger.info(
        f"Last reset was on {self._last_reset_date}, "
        f"but last Wednesday 5:00 was on {last_wednesday_date}. Performing reset..."
      )
      self._reset_all_statuses()
      self._save_last_reset_date(last_wednesday_date)

  async def _check_loop(self):
    """Основной цикл проверки времени."""
    while self._running:
      try:
        self._check_and_reset()
      except Exception as e:
        logger.error(f"Error in status reset check: {e}")

      await asyncio.sleep(60)

  def _check_and_reset(self):
    """Проверить время и сбросить статусы, если нужно."""
    now_moscow = datetime.now(MOSCOW_TZ)
    current_weekday = now_moscow.weekday()
    current_time = now_moscow.time()

    if current_weekday != RESET_DAY:
      return

    if current_time.hour != RESET_HOUR or current_time.minute != RESET_MINUTE:
      return

    reset_date = now_moscow.date()
    if self._last_reset_date == reset_date:
      return

    logger.info("Resetting all account statuses to NEED_TO_FARM")
    self._reset_all_statuses()
    self._save_last_reset_date(reset_date)

  def _reset_all_statuses(self):
    """Сбросить статус всех аккаунтов до NEED_TO_FARM."""
    try:
      table = self.account_lock._table
      all_accounts = table.all()

      reset_count = 0
      for account_data in all_accounts:
        login = account_data.get("login")
        if login and login != LAST_RESET_KEY:
          self.account_lock.set_field(login, "status", FarmStatus.NEED_TO_FARM)
          reset_count += 1

      logger.info(f"Reset status for {reset_count} accounts to NEED_TO_FARM")
    except Exception as e:
      logger.error(f"Failed to reset account statuses: {e}")

  def stop(self):
    """Остановить сервис."""
    self._running = False
    logger.info("StatusResetService stopped")
