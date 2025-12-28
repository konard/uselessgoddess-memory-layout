import ctypes
import os
import subprocess

dll_name = "pyautogui.dll"


def close_cs2_mutex():
  script_dir = os.path.dirname(os.path.abspath(__file__))
  project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
  dll_path = os.path.join(project_root, "data", dll_name)

  if not os.path.exists(dll_path):
    print(f"[-] Файл {dll_name} не найден!")
    print(f"[-] Путь к DLL: {dll_path}")
    return

  try:
    lib = ctypes.CDLL(dll_path)

    CloseAllMutexes = lib.CloseAllMutexes
    CloseAllMutexes.argtypes = []
    CloseAllMutexes.restype = ctypes.c_ulong

    print("[*] Вызываем CloseAllMutexes...")
    result = CloseAllMutexes()

    if result:
      print("[+] Успех! Мьютексы закрыты.")
    else:
      print("[-] Не удалось закрыть мьютексы через DLL, пробую через exe...")
      exe_path = os.path.join(project_root, "pyautogui.exe")
      if os.path.exists(exe_path):
        print(f"[*] Запускаю pyautogui.exe: {exe_path}")
        subprocess.run([exe_path], check=False)
      else:
        print(f"[-] Файл pyautogui.exe не найден: {exe_path}")

  except OSError as e:
    print(f"[-] Ошибка загрузки DLL: {e}")


if __name__ == "__main__":
  # Проверка на админа (обязательно для работы с чужими процессами)
  if not ctypes.windll.shell32.IsUserAnAdmin():
    print("[-] Запусти скрипт от имени Администратора!")
  else:
    close_cs2_mutex()
