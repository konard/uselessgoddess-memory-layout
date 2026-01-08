import asyncio
import json
import os
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

  def __init__(self, ctx=None):
    self.account_lock = AccountsLock()
    self.ctx = ctx
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
      logger.warn("StatusResetService already running")
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

    logger.info("Sending farm summary")
    self.send_farm_summary()

  def send_farm_summary(self):
    """Отправить отчет о фарме."""
    try:
      logger.info("Sending farm summary")
      report_path = "report.json"
      if not os.path.exists(report_path):
        logger.warning(f"{report_path} not found")
        return

      with open(report_path, encoding="utf-8") as f:
        data = json.load(f)

      cases = []
      drops = []

      for name, info in data.items():
        item = {
          "name": name,
          "price": info.get("price", 0),
          "amount": info.get("amount", 0),
        }
        if "Case" in name or "Terminal" in name:
          cases.append(item)
        else:
          drops.append(item)

      total_cases = sum(c["amount"] for c in cases)
      total_case_value = sum(c["price"] * c["amount"] for c in cases)
      avg_case_price = total_case_value / total_cases if total_cases > 0 else 0

      total_drops = sum(d["amount"] for d in drops)
      total_drop_value = sum(d["price"] * d["amount"] for d in drops)
      avg_drop_price = total_drop_value / total_drops if total_drops > 0 else 0

      guns = [
        d
        for d in drops
        if "Case" not in d["name"]
        and "Terminal" not in d["name"]
        and "Sticker" not in d["name"]
      ]

      top_5_drops = sorted(guns, key=lambda x: x["price"], reverse=True)[:5]
      sorted_cases = sorted(cases, key=lambda x: x["amount"], reverse=True)

      total_value = total_case_value + total_drop_value

      all_accounts_data = self.account_lock._table.all()
      real_accounts = [a for a in all_accounts_data if a.get("login") != LAST_RESET_KEY]
      total_accounts = len(real_accounts)

      # Формируем диапазон дат
      today = datetime.now().date()
      start_date = (
        self._last_reset_date if self._last_reset_date else (today - timedelta(days=7))
      )
      date_range = f"{start_date.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"

      lines = ["<pre>"]
      lines.append(
        "=--= \U0001f1e8\U0001f1f3 YACS PANEL | DROP REPORT \U0001f1e8\U0001f1f3 =--="
      )
      lines.append("")
      lines.append(f"Date: {date_range}")
      lines.append(f"Accounts: {total_accounts}")
      lines.append("")

      # --- Таблица кейсов ---
      # Case | Amount | Price | %
      col_case_w = 24
      col_amt_w = 6
      col_price_w = 8
      col_pct_w = 6

      header_case = f"{'Case':<{col_case_w}}| {'Amt':<{col_amt_w}}| {'Price':<{col_price_w}}| {'%':<{col_pct_w}}"  # noqa: E501
      sep_case = (
        "-" * col_case_w
        + "+"
        + "-" * (col_amt_w + 1)
        + "+"
        + "-" * (col_price_w + 1)
        + "+"
        + "-" * (col_pct_w + 1)
      )

      lines.append(header_case)
      lines.append(sep_case)

      if sorted_cases:
        for case in sorted_cases:
          name = case["name"].replace(" Case", "").replace("Package", "Pkg")
          if len(name) > col_case_w - 1:
            name = name[: col_case_w - 2] + "…"

          qty = case["amount"]
          price = case["price"]
          percent = (qty / total_cases) * 100 if total_cases > 0 else 0

          price_str = f"${case['price']:.2f}"
          lines.append(
            f"{name:<{col_case_w}}| {qty:<{col_amt_w}}| {price_str:<{col_price_w}}| {percent:<{col_pct_w}.0f}"  # noqa: E501
          )
      else:
        lines.append(
          f"{'No cases':<{col_case_w}}| {'0':<{col_amt_w}}| {'$0.00':<{col_price_w}}| {'0':<{col_pct_w}}"  # noqa: E501
        )

      lines.append(sep_case)
      lines.append("")

      col_skin_w = 32

      header_skin = (
        f"{'Skin':<{col_skin_w}}| {'Price':<{col_price_w}}| {'Amt':<{col_amt_w}}"
      )
      sep_skin = (
        "-" * col_skin_w + "+" + "-" * (col_price_w + 1) + "+" + "-" * (col_amt_w + 1)
      )

      lines.append(header_skin)
      lines.append(sep_skin)

      if top_5_drops:
        for item in top_5_drops:
          name = item["name"]
          replacements = {
            "(Factory New)": "- (FN)",
            "(Minimal Wear)": "- (MW)",
            "(Field-Tested)": "- (FT)",
            "(Well-Worn)": "- (WW)",
            "(Battle-Scarred)": "- (BS)",
          }
          for old, new in replacements.items():
            name = name.replace(old, new)

          name = name.replace("|", "-")

          if len(name) > col_skin_w - 1:
            display_name = name[: col_skin_w - 2] + "…"
          else:
            display_name = name

          qty = item["amount"]
          price = item["price"]
          price_str = f"${price:.2f}"

          lines.append(
            f"{display_name:<{col_skin_w}}| {price_str:<{col_price_w}}| {qty:<{col_amt_w}}"  # noqa: E501
          )
      else:
        lines.append(
          f"{'No drops':<{col_skin_w}}| {'0':<{col_amt_w}}| {'$0.00':<{col_price_w}}"
        )

      lines.append(sep_skin)
      lines.append("")

      # --- Итоги ---
      lines.append(f"→ Price of all drop: ~ {total_value:.1f}$.")
      lines.append(f"→ Total cases: {total_cases} pcs.")
      lines.append(
        f"→ AVG price of cases/all drop: {avg_case_price:.2f}$/{avg_drop_price:.2f}$."
      )

      lines.append("</pre>")
      msg = "\n".join(lines)

      if self.ctx:
        asyncio.create_task(self.ctx.send_message(msg))
      else:
        logger.warning("Context not available, cannot send telegram message")

    except Exception as e:
      logger.error(f"Failed to send farm summary: {e}")

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
