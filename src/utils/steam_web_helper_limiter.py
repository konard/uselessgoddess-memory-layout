#!/usr/bin/env python3
"""
steamwebhelper_limiter.py

Windows-focused helper to aggressively limit steamwebhelper.exe (and similar) processes
and close unnecessary top-level windows they own. Designed for farms with many Steam
instances.

Features:
- Periodically find processes by name (steamwebhelper.exe by default).
- Set process priority to IDLE and limit CPU affinity to a small set of cores.
- Optionally call EmptyWorkingSet to trim memory.
- Enumerate top-level windows owned by those processes and send WM_CLOSE to windows
  that match configurable filters (title substring or class name), or force-close.
- Logging, dry-run mode, and simple CLI configuration.

IMPORTANT:
- Requires admin (or at least enough privileges to change other processes'
affinity/priority and to send window messages).
- Use with care: killing or forcibly closing windows may break Steam or anti-cheat
  expectations. Test on one machine first.

Dependencies:
- psutil
- pywin32 (win32gui, win32con)

Install:
    pip install psutil pywin32

Usage example:
    python steamwebhelper_limiter.py --interval 5 --cores 0 --trim --force-close

"""

from __future__ import annotations

import argparse
import logging
import threading
import time

import psutil

try:
  import ctypes

  import win32con
  import win32gui
  import win32process
except Exception as e:
  raise RuntimeError("This script must be run on Windows with pywin32 installed") from e

# ----------------------------- Utility functions -----------------------------

DWORD = ctypes.c_ulong
_psapi = ctypes.WinDLL("psapi")
_kernel32 = ctypes.WinDLL("kernel32")


def empty_working_set(pid: int) -> bool:
  """Call EmptyWorkingSet on a process to encourage Windows
  to trim its memory."""
  PROCESS_SET_QUOTA = 0x0100
  PROCESS_QUERY_INFORMATION = 0x0400
  PROCESS_VM_READ = 0x0010
  h = _kernel32.OpenProcess(
    PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
    False,
    DWORD(pid),
  )
  if not h:
    return False
  try:
    res = _psapi.EmptyWorkingSet(h)
    return bool(res)
  finally:
    _kernel32.CloseHandle(h)


# ----------------------------- Window utilities -----------------------------


def enum_windows_for_pids(pids: set[int]) -> list[int]:
  """Return list of top-level window handles
  belonging to any of the given PIDs."""
  handles: list[int] = []

  def _enum(hwnd, extra):
    if not win32gui.IsWindowVisible(hwnd):
      return True
    try:
      _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
      return True
    if pid in pids:
      handles.append(hwnd)
    return True

  win32gui.EnumWindows(_enum, None)
  return handles


# ----------------------------- Core limiter class -----------------------------


class SteamWebHelperLimiter:
  def __init__(
    self,
    process_names: list[str] | None = None,
    cpu_cores: list[int] | None = None,
    set_priority_idle: bool = True,
    trim_memory: bool = False,
    close_windows: bool = True,
    window_title_blacklist: list[str] | None = None,
    window_class_blacklist: list[str] | None = None,
    force_close: bool = False,
    dry_run: bool = False,
    window_white_list: list[str] | None = None,
  ):
    self.process_names = process_names or [
      "steamwebhelper.exe",
      "gameoverlayui64.exe",
    ]
    self.cpu_cores = cpu_cores if cpu_cores is not None else [0]
    self.set_priority_idle = set_priority_idle
    self.trim_memory = trim_memory
    self.close_windows = close_windows
    self.window_title_blacklist = [
      s.lower()
      for s in (
        window_title_blacklist
        or ["Список друзей", "Список игр", "Steam", "Специальные предложения"]
      )
    ]
    self.window_white_list = [s.lower() for s in (window_white_list or ["Войти в Steam"])]
    self.window_class_blacklist = [s.lower() for s in (window_class_blacklist or [])]
    self.force_close = force_close
    self.dry_run = dry_run

  def _matching_processes(self) -> list[psutil.Process]:
    procs = []
    for p in psutil.process_iter(attrs=["pid", "name"]):
      try:
        name = (p.info.get("name") or "").lower()
      except Exception:
        continue
      if name in [n.lower() for n in self.process_names]:
        procs.append(p)
    return procs

  def _limit_proc(self, p: psutil.Process):
    pid = p.pid
    name = p.name()
    logging.debug(f"Processing PID={pid} name={name}")
    if self.dry_run:
      logging.info(f"[dry-run] Would limit PID {pid} ({name})")
      return

    # set priority
    try:
      if self.set_priority_idle:
        try:
          p.nice(psutil.IDLE_PRIORITY_CLASS)
        except Exception:
          # fallback for older psutil version
          p.nice(psutil.IDLE_PRIORITY_CLASS)
        logging.debug(f"Set idle priority for PID {pid}")
    except Exception as e:
      logging.warning(f"Failed to set priority for PID {pid}: {e}")

    # set cpu affinity
    try:
      if self.cpu_cores is not None:
        all_cores = psutil.cpu_count(logical=True) or 1
        # clamp
        valid = [c for c in self.cpu_cores if 0 <= c < all_cores]
        if valid:
          p.cpu_affinity(valid)
          logging.debug(f"Set CPU affinity {valid} for PID {pid}")
    except Exception as e:
      logging.warning(f"Failed to set affinity for PID {pid}: {e}")

    # trim memory
    try:
      if self.trim_memory:
        ok = empty_working_set(pid)
        logging.debug(f"EmptyWorkingSet for PID {pid} -> {ok}")
    except Exception as e:
      logging.warning(f"Failed to trim memory for PID {pid}: {e}")

  def _close_windows_for_pids(self, pids: set[int]):
    if not pids:
      return
    handles = enum_windows_for_pids(pids)
    for h in handles:
      try:
        title = win32gui.GetWindowText(h) or ""
        cls = win32gui.GetClassName(h) or ""
      except Exception:
        continue
      low_title = title.lower()
      low_cls = cls.lower()

      should_close = False
      # If any blacklist substring present in title -> close
      for bad in self.window_title_blacklist:
        if bad in low_title and bad not in self.window_white_list:
          should_close = True
          break
      for bad in self.window_class_blacklist:
        if bad in low_cls:
          should_close = True
          break

      if should_close:
        logging.debug(f"Closing window HWND={h} title='{title}' class='{cls}'")
        if self.dry_run:
          continue
        try:
          win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
          # optionally force destroy after delay
          if self.force_close:
            # give it a short grace period then force
            def _force():
              time.sleep(1)
              try:
                # FIXME: B023
                if win32gui.IsWindow(h):
                  win32gui.PostMessage(h, win32con.WM_QUIT, 0, 0)
              except Exception:
                pass

            threading.Thread(target=_force, daemon=True).start()
        except Exception as e:
          logging.warning(f"Failed to close window {h}: {e}")

  def run_once(self):
    procs = self._matching_processes()
    if not procs:
      logging.debug("No matching processes found")
      return
    pids = set()
    for p in procs:
      try:
        self._limit_proc(p)
        pids.add(p.pid)
      except psutil.NoSuchProcess:
        continue
    if self.close_windows:
      self._close_windows_for_pids(pids)

  def run_loop(self, interval: float = 5.0):
    logging.info("Starting limiter loop (Ctrl-C to stop)")
    try:
      while True:
        try:
          self.run_once()
        except Exception:
          logging.exception("Error during run_once")
          if interval < 0:
            break
        time.sleep(interval)
    except KeyboardInterrupt:
      logging.info("Stopped by user")


# ----------------------------- CLI -----------------------------


def parse_args():
  p = argparse.ArgumentParser(
    description="Limit steamwebhelper processes and close windows"
  )
  p.add_argument(
    "--interval", "-i", type=float, default=5.0, help="Loop interval seconds"
  )
  p.add_argument(
    "--cores",
    "-c",
    type=int,
    nargs="*",
    help="CPU cores to allow (e.g. -c 0 1)",
  )
  p.add_argument("--no-priority", action="store_true", help="Do not set idle priority")
  p.add_argument(
    "--trim", action="store_true", help="Call EmptyWorkingSet to trim memory"
  )
  p.add_argument("--no-close", action="store_true", help="Do not close windows")
  p.add_argument(
    "--title-blacklist",
    nargs="*",
    help="Window title substrings to close",
  )
  p.add_argument("--class-blacklist", nargs="*", help="Window class names to close")
  p.add_argument(
    "--force-close",
    action="store_true",
    help="Force-close windows after a short delay",
  )
  p.add_argument(
    "--dry-run",
    action="store_true",
    help="Don't change anything, just log what would be done",
  )
  p.add_argument(
    "--process-names",
    nargs="*",
    help="Process names to target (default: steamwebhelper.exe)",
  )
  return p.parse_args()


def limit_steam_web_helper(
  process_names: list[str] | None = None,
  cpu_cores: list[int] | None = None,
  set_priority_idle: bool = True,
  trim_memory: bool = True,
  close_windows: bool = False,
  window_title_blacklist: list[str] | None = None,
  window_class_blacklist: list[str] | None = None,
  force_close: bool = True,
  dry_run: bool = False,
  white: list[str] | None = None,
):
  logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

  limiter = SteamWebHelperLimiter(
    process_names=process_names,
    cpu_cores=cpu_cores,
    set_priority_idle=not set_priority_idle,
    trim_memory=trim_memory,
    close_windows=not close_windows,
    window_title_blacklist=window_title_blacklist,
    window_class_blacklist=window_class_blacklist,
    force_close=force_close,
    dry_run=dry_run,
    window_white_list=white,
  )
  limiter.run_once()


if __name__ == "__main__":
  limit_steam_web_helper(force_close=True)
