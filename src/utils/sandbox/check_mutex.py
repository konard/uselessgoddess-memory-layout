import os
import re
import subprocess

# --- КОНФИГУРАЦИЯ ---
TARGET_PROCESS = "cs2.exe"
HANDLE_TOOL_NAME = "handle64.exe"
# Ищем мьютекс, содержащий это слово
MUTEX_PATTERN = "singleton_mutex"
# --------------------


def get_handle_tool_path():
  script_dir = os.path.dirname(os.path.abspath(__file__))
  path = os.path.join(script_dir, HANDLE_TOOL_NAME)
  if os.path.exists(path):
    return path
  if os.path.exists(HANDLE_TOOL_NAME):
    return HANDLE_TOOL_NAME
  return None


def kill_multiple_mutexes():
  handle_path = get_handle_tool_path()
  if not handle_path:
    print(f"[-] Не найден {HANDLE_TOOL_NAME} (проверьте папку src/utils/sandbox/)")
    return

  print(f"[*] Сканируем ВСЕ процессы {TARGET_PROCESS}...")

  # 1. Получаем общий список хэндлов для всех процессов cs2.exe
  cmd_list = [handle_path, "-a", "-p", TARGET_PROCESS, "-nobanner", "-accepteula"]
  try:
    result = subprocess.run(
      cmd_list, capture_output=True, text=True, encoding="cp866", errors="replace"
    )
  except Exception as e:
    print(f"[-] Ошибка запуска handle64: {e}")
    return

  lines = result.stdout.splitlines()

  # Структура для хранения целей: список словарей
  targets_to_kill = []

  current_pid = None

  # Регулярки
  pid_regex = re.compile(r"pid:\s*(\d+)", re.IGNORECASE)
  handle_regex = re.compile(r"^\s*([0-9A-Fa-f]+):\s+Mutant\s+(.*)", re.IGNORECASE)

  # 2. Парсим вывод
  for line in lines:
    # Если строка содержит имя процесса и PID - обновляем текущий PID
    # Handle.exe группирует вывод: сначала заголовок процесса, потом его хэндлы
    if TARGET_PROCESS in line:
      pid_match = pid_regex.search(line)
      if pid_match:
        current_pid = pid_match.group(1)
      continue

    # Если мы внутри блока какого-то PID, ищем мьютекс
    if current_pid:
      match = handle_regex.search(line)
      if match:
        hex_id = match.group(1)
        name = match.group(2).strip()

        if MUTEX_PATTERN.lower() in name.lower():
          # Добавляем в список на уничтожение
          targets_to_kill.append({"pid": current_pid, "handle": hex_id, "name": name})

  if not targets_to_kill:
    print(f"[-] Мьютексы '*{MUTEX_PATTERN}*' не найдены ни в одном процессе.")
    return

  print(f"[+] Найдено целей: {len(targets_to_kill)}")
  print("=" * 60)

  # 3. Закрываем всё, что нашли
  success_count = 0
  for target in targets_to_kill:
    pid = target["pid"]
    hid = target["handle"]
    name = target["name"]

    print(f"[*] PID: {pid} | Handle: {hid} | Закрываем...")

    close_cmd = [handle_path, "-c", hid, "-p", pid, "-y", "-nobanner", "-accepteula"]

    res = subprocess.run(
      close_cmd, capture_output=True, text=True, encoding="cp866", errors="replace"
    )

    if res.returncode == 0:
      print("    -> [OK] Успешно закрыт.")
      success_count += 1
    else:
      print(f"    -> [ERROR] Ошибка: {res.stdout.strip()}")

  print("=" * 60)
  print(f"[*] Итог: Закрыто {success_count} из {len(targets_to_kill)} мьютексов.")


if __name__ == "__main__":
  kill_multiple_mutexes()
  input("\nНажмите Enter, чтобы выйти...")
