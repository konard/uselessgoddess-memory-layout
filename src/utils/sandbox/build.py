import os
import subprocess
import sys

# === НАСТРОЙКИ ===
# Укажи путь к папке с исходниками, если они не рядом
SOURCE_DIR = r"."
OUTPUT_DLL = "pyautogui.dll"
# =================


def find_vcvars64():
  """Ищет vcvars64.bat через vswhere (официальная утилита MS)"""
  vswhere_path = os.path.expandvars(
    r"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  )

  if not os.path.exists(vswhere_path):
    # Если vswhere нет, попробуем тупой перебор стандартных путей
    years = ["2026", "2022", "2019", "2017"]
    editions = ["Community", "Professional", "Enterprise"]
    for year in years:
      for ed in editions:
        path = rf"C:\Program Files\Microsoft Visual Studio\{year}\{ed}\VC\Auxiliary\Build\vcvars64.bat"
        if os.path.exists(path):
          return path
    return None

  try:
    # Спрашиваем у vswhere путь установки VS
    output = subprocess.check_output(
      [
        vswhere_path,
        "-latest",
        "-products",
        "*",
        "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
        "-property",
        "installationPath",
      ],
      encoding="utf-8",
      errors="ignore",
    ).strip()

    if output:
      bat_path = os.path.join(output, r"VC\Auxiliary\Build\vcvars64.bat")
      if os.path.exists(bat_path):
        return bat_path
  except Exception as e:
    print(f"[-] Ошибка при поиске VS: {e}")

  return None


def build():
  script_dir = os.path.dirname(os.path.abspath(__file__))
  project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
  data_dir = os.path.join(project_root, "data")
  os.makedirs(data_dir, exist_ok=True)
  output_path = os.path.join(data_dir, OUTPUT_DLL)

  abs_source = os.path.join(project_root, "src", "utils", "sandbox")
  os.chdir(abs_source)

  if not os.path.exists("main.cpp"):
    print(f"[-] Не вижу main.cpp в папке {abs_source}")
    return

  # 3. Ищем Visual Studio
  print("[*] Ищу компилятор MSVC...")
  vcvars_bat = find_vcvars64()

  if not vcvars_bat:
    print("[-] Не удалось найти Visual Studio (vcvars64.bat).")
    print(
      "    Убедись, что установлена 'Разработка классических приложений на C++'."
    )
    return

  print(f"[+] Нашел: {vcvars_bat}")

  # 4. Формируем команду
  build_cmd = f'cl main.cpp /LD /std:c++20 /DUNICODE /D_UNICODE /DLIB_CS2CH /O2 /nologo /Fe:"{output_path}" /link ntdll.lib'

  full_command = f'"{vcvars_bat}" && {build_cmd}'

  print(f"[*] Запускаю сборку {OUTPUT_DLL}...")

  # 5. Выполняем
  try:
    subprocess.check_call(full_command, shell=True)

    print("\n" + "=" * 30)
    print(f"[+] ГОТОВО! DLL лежит тут:\n    {output_path}")
    print("=" * 30)

    for ext in [".obj", ".exp", ".lib"]:
      try:
        os.remove(output_path.replace(".dll", ext))
      except:  # noqa: E722
        pass
      try:
        os.remove("main.obj")
      except:  # noqa: E722
        pass

  except subprocess.CalledProcessError:
    print("[-] Ошибка во время компиляции.")


if __name__ == "__main__":
  build()
