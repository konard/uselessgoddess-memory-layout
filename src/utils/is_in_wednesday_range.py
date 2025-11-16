from datetime import datetime, timedelta


def is_in_wednesday_range(generation_time: int) -> bool:
  """
  Проверяет, находится ли generationTime в промежутке с предыдущей среды по следующую среду.

  Args:
      generation_time: Unix timestamp в секундах

  Returns:
      True если generationTime находится в промежутке, False иначе
  """
  # Преобразуем timestamp в datetime
  gen_dt = datetime.fromtimestamp(generation_time)
  today = datetime.now()
  today = today.replace(hour=0, minute=0, second=0, microsecond=0)

  # Находим предыдущую среду (weekday() для среды = 2)
  days_since_wednesday = (today.weekday() - 2) % 7
  if days_since_wednesday == 0:  # Если сегодня среда
    days_since_wednesday = 7  # Берем предыдущую среду (неделю назад)

  previous_wednesday = today - timedelta(days=days_since_wednesday)
  previous_wednesday = previous_wednesday.replace(
    hour=0, minute=0, second=0, microsecond=0
  )

  # Находим следующую среду
  days_until_wednesday = (2 - today.weekday()) % 7
  if days_until_wednesday == 0:  # Если сегодня среда
    days_until_wednesday = 7  # Берем следующую среду (через неделю)

  next_wednesday = today + timedelta(days=days_until_wednesday)
  next_wednesday = next_wednesday.replace(
    hour=0, minute=0, second=0, microsecond=0
  )

  # Проверяем, находится ли generationTime в промежутке [previous_wednesday, next_wednesday)
  return previous_wednesday <= gen_dt < next_wednesday
