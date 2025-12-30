import os
import random
import string
import subprocess


def generate_random_id(length=8):
  return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def build_cs2_launch_args(
  steam_path: str,
  appid: str = "730",
  win_w: int = 360,
  win_h: int = 270,
) -> list[str]:
  steam_args = [
    steam_path,
    "-dev",
    "-nofriendsui",
    "-vgui",
    "-noreactlogin",
    "-noverifyfiles",
    "-nobootstrapupdate",
    "-skipinitialbootstrap",
    "-norepairfiles",
    "-overridepackageurl",
    "-disable-winh264",
    "-applaunch",
    appid,
    "+exec",
    "yacs.cfg",
    "+fps_max",
    "30",
    "-allowmultiple",
    "-window",
    "-w",
    str(win_w),
    "-h",
    str(win_h),
    "-language",
    "russian",
    "-swapcores",
    "-noqueuedload",
    "-vrdisable",
    "-nopreload",
    "-limitvsconst",
    "-softparticlesdefaultoff",
    "-nohltv",
    "-nosound",
    "-novid",
    "+violence_hblood",
    "0",
    "+sethdmodels",
    "0",
    "+mat_disable_fancy_blending",
    "1",
    "+r_dynamic",
    "0",
  ]

  return steam_args


def launch_instance(username, steam_path, w, h):
  base_data_dir = os.path.join(os.getcwd(), "data", "sandboxes")
  steam_dir = os.path.dirname(steam_path)

  ipc_name = f"{username}_ipc_{generate_random_id(4)}"
  vproject_name = f"steam_multi_chesalus_{username}"

  sandbox_root = os.path.join(base_data_dir, username)
  user_profile_fake = sandbox_root
  local_app_data = os.path.join(sandbox_root, "AppData", "Local")
  temp_dir = os.path.join(local_app_data, "Temp")

  os.makedirs(temp_dir, exist_ok=True)

  env = os.environ.copy()

  env["USERPROFILE"] = user_profile_fake
  env["LOCALAPPDATA"] = local_app_data
  env["APPDATA"] = os.path.join(sandbox_root, "AppData", "Roaming")
  env["TEMP"] = temp_dir
  env["TMP"] = temp_dir

  env["VPROJECT"] = vproject_name

  env["steam_master_ipc_name_override"] = ipc_name

  steam_exe_unix = steam_path.replace("\\", "/")
  env["ValvePlatformMutex"] = steam_exe_unix

  env["SteamAppId"] = "730"
  env["SteamGameId"] = "730"
  env["SteamEnv"] = "1"

  cmd = build_cs2_launch_args(steam_path, win_w=w, win_h=h)

  # Внедряем аргументы изоляции
  cmd.insert(1, "-master_ipc_name_override")
  cmd.insert(2, ipc_name)

  # Добавляем -silent для тихого запуска Steam, если его нет
  if "-silent" not in cmd:
    cmd.insert(3, "-silent")

  return subprocess.Popen(cmd, env=env, cwd=steam_dir, close_fds=True)
