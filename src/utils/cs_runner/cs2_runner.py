import argparse
import os
import sys
import time
import subprocess

# Local imports
# Добавляем текущую директорию в путь, чтобы импорты работали корректно
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
  sys.path.insert(0, current_dir)

try:
  import windows_utils
  import process_utils
  import steam_launch
except ImportError:
  # Fallback for when running from a different context where path might not be set correctly immediately
  sys.path.append(os.path.dirname(__file__))
  import windows_utils
  import process_utils
  import steam_launch


def main() -> int:
  # windows_utils.hide_console_window()
  print("Runner initialized.")

  parser = argparse.ArgumentParser()
  parser.add_argument("--steamPath", required=True)
  parser.add_argument("--quiet", action="store_true")
  parser.add_argument("--login", type=str)
  parser.add_argument("--w", type=int, default=360)
  parser.add_argument("--h", type=int, default=270)
  parser.add_argument("--hook_dll", required=True)
  parser.add_argument("--sandboxiePath", type=str, help="Path to Start.exe")
  parser.add_argument("--box", type=str, help="Sandbox Name")
  parser.add_argument(
    "--experimental", action="store_true", help="Use experimental launch method"
  )

  args = parser.parse_args()

  console_title = f"Runner-{args.login or 'Unknown'}"
  windows_utils.set_console_title(console_title)

  # Job object handle to keep it alive
  _job_handle = None
  if os.name == "nt" and not args.box:
    _job_handle = windows_utils.setup_kill_on_job_close()

  baseline_steam_pids = process_utils.get_pids_by_name("steam.exe")
  print(f"Baseline Steam PIDs: {baseline_steam_pids}")

  if args.experimental:
    print(f"Launching instance with experimental mode for {args.login}")
    proc = steam_launch.launch_instance(
      args.login, args.steamPath, args.w, args.h
    )
  else:
    opts = steam_launch.build_cs2_launch_args(
      args.steamPath,
      win_w=args.w,
      win_h=args.h,
      sandboxie_path=args.sandboxiePath,
      box_name=args.box,
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

  print("Launch command executed.")

  if proc.pid is not None:
    # Wait for CS2 process and window
    print("Waiting for CS2 process...")
    cs2_pids = process_utils.wait_for_child_processes(proc.pid)

    if cs2_pids:
      if process_utils.wait_for_window_visibility(cs2_pids, timeout=120):
        print("CS2 window detected. Proceeding to inject.")
        time.sleep(20)  # Small buffer
      else:
        print("CS2 window not detected. Proceeding anyway...")
    else:
      print("CS2 process not found. Proceeding with default delay...")
      time.sleep(60)

    syswow64 = os.path.join(
      os.environ.get("SystemRoot", "C:\\Windows"), "SysWOW64"
    )
    rundll32_path = os.path.join(syswow64, "rundll32.exe")

    if not os.path.exists(rundll32_path):
      rundll32_path = "rundll32.exe"

    hook_cmd = []
    time.sleep(10)
    if args.box and args.sandboxiePath:
      print(f"Injecting into Steam PID {proc.pid} (Inside Box)...")
      hook_cmd = [
        args.sandboxiePath,
        f"/box:{args.box}",
        "/silent",
        rundll32_path,
        f"{args.hook_dll},Inject",
        str(proc.pid),
        str(args.login),
      ]
    else:
      print(f"Injecting into Steam PID {proc.pid} (Native)...")
      hook_cmd = [
        rundll32_path,
        f"{args.hook_dll},Inject",
        str(proc.pid),
        str(args.login),
      ]

    try:
      injector = subprocess.run(
        hook_cmd,
        capture_output=True,
        text=True,
      )
      print(f"Injector output: {injector.stdout}")
      if injector.stderr:
        print(f"Injector stderr: {injector.stderr}")

      if injector.returncode == 0:
        print("Inject command sent.")
      else:
        print(f"Inject failed: {injector.stderr}")
    except Exception as e:
      print(f"Inject exception: {e}")

  else:
    print("Timeout: New Steam process not found.")

  print("Monitoring target Steam process...")

  if proc.pid is not None:
    try:
      while process_utils.is_process_running(proc.pid):
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
