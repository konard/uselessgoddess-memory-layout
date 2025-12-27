import os
import sys
import subprocess
import winreg
import random
import string
import time

# --- НАСТРОЙКИ ---
# Путь к папке Steam (где лежит steam.exe)
STEAM_DIR = r"P:\steam"
STEAM_EXE = os.path.join(STEAM_DIR, "steam.exe")

# Папка для хранения данных (песочницы)
BASE_DATA_DIR = os.path.join(os.getenv("LOCALAPPDATA"), "SteamSandboxes")


def generate_random_id(length=8):
  return "".join(
    random.choices(string.ascii_lowercase + string.digits, k=length)
  )


def set_autologin_user(username):
  """Меняет пользователя в реестре перед запуском."""
  try:
    key_path = r"Software\Valve\Steam"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
      winreg.SetValueEx(key, "AutoLoginUser", 0, winreg.REG_SZ, username)
      winreg.SetValueEx(key, "RememberPassword", 0, winreg.REG_DWORD, 1)
      # Иногда помогает сброс PID старого процесса в реестре
      try:
        winreg.DeleteValue(key, "ActiveProcess")
      except:  # noqa: E722
        pass
    print(f"[*] Реестр: AutoLoginUser установлен на {username}")
  except Exception as e:
    print(f"[!] Ошибка записи в реестр: {e}")


def launch_instance(username, instance_index):
  # Уникальные идентификаторы
  ipc_name = f"{username}_ipc_{generate_random_id(4)}"
  vproject_name = "steam_multi_chesalus"

  # Структура папок
  sandbox_root = os.path.join(BASE_DATA_DIR, username)
  user_profile_fake = sandbox_root
  local_app_data = os.path.join(sandbox_root, "AppData", "Local")
  temp_dir = os.path.join(local_app_data, "Temp")

  os.makedirs(temp_dir, exist_ok=True)

  # === МАГИЯ ОКРУЖЕНИЯ (Environment Spoofing) ===
  env = os.environ.copy()

  # 1. Изоляция путей (файловая система)
  env["USERPROFILE"] = user_profile_fake
  env["LOCALAPPDATA"] = local_app_data
  env["APPDATA"] = os.path.join(sandbox_root, "AppData", "Roaming")
  env["TEMP"] = temp_dir
  env["TMP"] = temp_dir

  # 2. Изоляция движка Source 2 (CS2) - КЛЮЧЕВОЙ МОМЕНТ
  # VPROJECT заставляет движок думать, что это разные проекты
  env["VPROJECT"] = vproject_name

  # IPC Override - чтобы игра знала, с каким именно стимом общаться
  env["steam_master_ipc_name_override"] = ipc_name

  # ValvePlatformMutex - имитируем поведение FSM (путь к exe)
  # Важно: слеши должны быть прямыми (/), движок чувствителен к этому
  steam_exe_unix = STEAM_EXE.replace("\\", "/")
  env["ValvePlatformMutex"] = steam_exe_unix

  # Дополнительные флаги из логов FSM
  env["SteamAppId"] = "730"
  env["SteamGameId"] = "730"
  env["SteamEnv"] = "1"

  # === СБОРКА КОМАНДЫ ЗАПУСКА ===
  # Сначала аргументы Steam, потом -applaunch 730, потом аргументы ИГРЫ
  cmd = [
    STEAM_EXE,
    # -- Аргументы Steam --
    "-nofriendsui",
    "-noreactlogin",
    "-noverifyfiles",
    "-nobootstrapupdate",
    "-skipinitialbootstrap",
    "-norepairfiles",
    "-no-dwrite",
    "-master_ipc_name_override",
    ipc_name,  # Изоляция IPC
    # -- Запуск CS2 --
    "-applaunch",
    "730",  # 730 - ID CS2
    # -- Аргументы CS2 (идут после applaunch) --
    "-allowmultiple",  # <--- ВАЖНО: Разрешает несколько окон самой игры
    "-steam",  # Говорит игре, что она запущена через Steam
    "-windowed",
    "-w",
    "640",
    "-h",
    "480",  # Оконный режим 640x480
    "-novid",  # Без заставки
    "-nosound",  # Без звука (чтобы не сойти с ума от 10 окон)
    "-low",  # Низкий приоритет
    "-nojoy",  # Отключить джойстик
    "-silent",
  ]

  print(f"\n[*] Запуск Instance #{instance_index} ({username})...")
  print(f"    IPC: {ipc_name}")
  print(f"    VPROJECT: {vproject_name}")

  # Запускаем процесс
  subprocess.Popen(cmd, env=env, cwd=STEAM_DIR, close_fds=True)


def main():
  if not os.path.exists(STEAM_EXE):
    print(f"[!] Ошибка: Не найден {STEAM_EXE}")
    print("Отредактируйте путь STEAM_DIR в скрипте.")
    return

  print("=== CS2 & Steam Multi-Instance Launcher ===")

  # Получаем список аккаунтов
  accounts = ["hydshizarabotoi"]

  for i, user in enumerate(accounts, 1):
    # 1. Меняем реестр для автологина
    set_autologin_user(user)

    # 2. Запускаем Steam + CS2
    launch_instance(user, i)

    # 3. Ждем.
    # FSM запускает быстро, но для надежности лучше 10-15 сек,
    # пока Steam прочитает реестр и залочит свои файлы.
    print("[*] Ждем 15 сек перед следующим окном...")
    time.sleep(15)

  print("\n[*] Все окна запущены.")


if __name__ == "__main__":
  main()
