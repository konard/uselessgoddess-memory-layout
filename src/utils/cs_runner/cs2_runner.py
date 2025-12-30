import argparse
import os
import subprocess
import sys
import time

# Local imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
  sys.path.insert(0, current_dir)

try:
  import process_utils
  import steam_launch
  import windows_utils
except ImportError:
  sys.path.append(os.path.dirname(__file__))
  import process_utils
  import steam_launch
  import windows_utils


def main() -> int:
  print("Runner initialized.")

  parser = argparse.ArgumentParser()
  parser.add_argument("--steamPath", required=True)
  parser.add_argument("--quiet", action="store_true")
  parser.add_argument("--login", type=str)
  parser.add_argument("--w", type=int, default=360)
  parser.add_argument("--h", type=int, default=270)
  parser.add_argument("--hook_dll", required=True)
  parser.add_argument(
    "--experimental", action="store_true", help="Use experimental launch method"
  )

  args = parser.parse_args()

  console_title = f"Runner-{args.login or 'Unknown'}"
  windows_utils.set_console_title(console_title)

  _job_handle = None
  if os.name == "nt":
    _job_handle = windows_utils.setup_kill_on_job_close()

  print(f"Launching Steam for {args.login}...")

  if args.experimental:
    proc = steam_launch.launch_instance(args.login, args.steamPath, args.w, args.h)
  else:
    opts = steam_launch.build_cs2_launch_args(
      args.steamPath,
      win_w=args.w,
      win_h=args.h,
    )
    proc = subprocess.Popen(
      opts,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      encoding="utf-8",
      errors="replace",
      cwd=os.getcwd(),
      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

  print(f"Launch command executed. Initial PID: {proc.pid}")

  target_steam_pid = proc.pid  # По умолчанию (если вдруг CS2 не найдется)

  if proc.pid is not None:
    print("Waiting for CS2 process...")
    cs2_pids = process_utils.wait_for_child_processes(proc.pid)

    if cs2_pids:
      real_parent_steam = process_utils.get_process_parent_pid(cs2_pids[0])

      if real_parent_steam:
        print(
          f"Detected actual Game Parent (Steam) PID: {real_parent_steam}"
          + f"(from CS2 PID: {cs2_pids[0]})"
        )
        target_steam_pid = real_parent_steam
      else:
        print("Could not resolve CS2 parent, using initial PID.")

      if process_utils.wait_for_window_visibility(cs2_pids, timeout=120):
        print("CS2 window detected. Proceeding to inject.")
      else:
        print("CS2 window not detected. Proceeding anyway...")
    else:
      print("CS2 process not found. Proceeding with default delay...")
      time.sleep(60)

    rundll32_path = "rundll32.exe"

    hook_cmd = []
    time.sleep(5)

    print(f"Injecting into Steam PID {target_steam_pid}...")
    hook_cmd = [
      rundll32_path,
      f"{args.hook_dll},Inject",
      str(target_steam_pid),
      str(args.login),
    ]

    try:
      if not process_utils.is_process_running(target_steam_pid):
        print(
          f"Warning: Target PID {target_steam_pid} appears to be dead before injection!"
        )

      injector = subprocess.run(
        hook_cmd,
        capture_output=True,
        text=True,
      )

      if injector.stdout:
        print(f"Injector stdout: {injector.stdout}")
      if injector.stderr:
        print(f"Injector stderr: {injector.stderr}")

      if injector.returncode == 0:
        print("Inject command sent.")
      else:
        print(f"Inject returned non-zero code: {injector.returncode}")

    except Exception as e:
      print(f"Inject exception: {e}")

  else:
    print("Timeout: New Steam process not found.")

  print("Monitoring target Steam process...")

  monitor_pid = target_steam_pid if target_steam_pid else proc.pid

  if monitor_pid:
    try:
      while process_utils.is_process_running(monitor_pid):
        time.sleep(5)
      print("Target Steam process terminated. Exiting.")
    except KeyboardInterrupt:
      pass
  else:
    print("No target process to monitor. Exiting.")

  return 0


if __name__ == "__main__":
  try:
    sys.exit(main())
  except KeyboardInterrupt:
    pass
  except Exception as e:
    import traceback

    traceback.print_exc()
    print(f"Critical error: {e}")
    input("Press Enter to exit...")
