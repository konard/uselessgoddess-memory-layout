import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

try:
  import pathspec
except ImportError:
  print("Error: pathspec library is required. Install it with: pip install pathspec")
  exit(1)

RELEASE_DIR = "release"
ZIP_NAME = f"yacsp_release_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

NON_GIT_EXE_FILES = [
  "yacsp.exe",
  "cs2_runner.exe",
]

EMPTY_FILES = [
  "logpass.txt",
  "accounts.json",
]

SETTINGS_TEMPLATE = {
  "license_key": "",
  "trade_url": "",
  "steam_path": "",
  "cs_path": "",
  "win_w": 360,
  "win_h": 270,
  "experimental_launch": False,
  "telegram_token": "",
  "telegram_whitelist": [],
  "collect_available_steam_games_on_login": False,
  "extension_ids": [],
  "match_mode": "tie",
  "times_to_shuffle": 3,
  "times_to_brute_force": 3,
  "farm_until": None,
  "overfarm": None,
}


def get_git_tracked_files(root_path: Path) -> set[Path] | None:
  try:
    result = subprocess.run(
      ["git", "ls-files"],
      cwd=root_path,
      capture_output=True,
      text=True,
      check=True,
    )
    tracked = set()
    for line in result.stdout.strip().split("\n"):
      if line:
        tracked.add(root_path / line.replace("/", os.sep))
    return tracked
  except (subprocess.CalledProcessError, FileNotFoundError):
    return None


def load_gitignore_spec(root_path: Path) -> pathspec.PathSpec:
  gitignore_path = root_path / ".gitignore"
  if not gitignore_path.exists():
    return pathspec.PathSpec.from_lines("gitwildmatch", [])

  with open(gitignore_path, encoding="utf-8") as f:
    patterns = f.read().splitlines()

  return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def should_include_file(
  file_path: Path,
  root_path: Path,
  gitignore_spec: pathspec.PathSpec,
  git_tracked: set[Path] | None,
) -> bool:
  if git_tracked is not None:
    return file_path in git_tracked

  rel_path = file_path.relative_to(root_path)
  rel_path_str = str(rel_path).replace("\\", "/")

  return not gitignore_spec.match_file(rel_path_str)


def copy_file(src: Path, dst: Path):
  dst.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(src, dst)


def create_release():
  root_path = Path(".").resolve()
  git_tracked = get_git_tracked_files(root_path)
  gitignore_spec = load_gitignore_spec(root_path)

  if git_tracked:
    print("Using git ls-files to determine tracked files...")
  else:
    print("Git not available, using .gitignore patterns...")

  if os.path.exists(RELEASE_DIR):
    shutil.rmtree(RELEASE_DIR)
  os.makedirs(RELEASE_DIR, exist_ok=True)

  print("Scanning files...")
  files_to_copy = []
  data_dir = root_path / "data"

  if git_tracked:
    for file_path in git_tracked:
      if file_path.exists() and file_path.is_file():
        rel_path = file_path.relative_to(root_path)
        is_in_data = data_dir in file_path.parents or file_path.parent == data_dir
        if is_in_data:
          files_to_copy.append((file_path, rel_path))

    for exe_file in NON_GIT_EXE_FILES:
      exe_path = root_path / exe_file
      if exe_path.exists() and exe_path.is_file():
        rel_path = exe_path.relative_to(root_path)
        files_to_copy.append((exe_path, rel_path))
        if exe_path not in git_tracked:
          print(f"  Adding non-git exe: {exe_file}")
  else:
    for root, dirs, files in os.walk(root_path):
      root_path_obj = Path(root)

      dirs[:] = [
        d
        for d in dirs
        if not gitignore_spec.match_file(
          str((root_path_obj / d).relative_to(root_path)).replace("\\", "/")
        )
      ]

      for file in files:
        file_path = root_path_obj / file
        rel_path = file_path.relative_to(root_path)

        is_in_data = data_dir in file_path.parents or file_path.parent == data_dir
        is_exe_allowed = file_path.name in NON_GIT_EXE_FILES

        if is_in_data:
          should_include = should_include_file(
            file_path, root_path, gitignore_spec, git_tracked
          )
          if should_include:
            files_to_copy.append((file_path, rel_path))
        elif is_exe_allowed:
          files_to_copy.append((file_path, rel_path))

  print(f"Found {len(files_to_copy)} files to include")

  print("\nCopying files...")
  copied_count = 0
  for src_path, rel_path in files_to_copy:
    dst_path = Path(RELEASE_DIR) / rel_path
    try:
      copy_file(src_path, dst_path)
      copied_count += 1
      if copied_count % 50 == 0:
        print(f"  Copied {copied_count}/{len(files_to_copy)} files...")
    except Exception as e:
      print(f"⚠ Warning: Failed to copy {rel_path}: {e}")

  print(f"✓ Copied {copied_count} files")

  print("\nCreating empty files...")
  for file_name in EMPTY_FILES:
    file_path = Path(RELEASE_DIR) / file_name
    if not file_path.exists():
      file_path.touch()
      print(f"✓ Created {file_name}")

  print("\nCreating settings.json template...")
  import json

  settings_path = Path(RELEASE_DIR) / "settings.json"
  if not settings_path.exists():
    with open(settings_path, "w", encoding="utf-8") as f:
      json.dump(SETTINGS_TEMPLATE, f, indent=2, ensure_ascii=False)
    print("✓ Created settings.json")

  print(f"\n✓ Release created in folder: {RELEASE_DIR}")


def create_zip():
  if not os.path.exists(RELEASE_DIR):
    print(f"❌ Folder {RELEASE_DIR} does not exist!")
    return

  print(f"\nCreating archive {ZIP_NAME}...")
  file_count = 0
  with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, _, files in os.walk(RELEASE_DIR):
      for file in files:
        file_path = Path(root) / file
        arc_name = file_path.relative_to(RELEASE_DIR)
        zipf.write(file_path, arc_name)
        file_count += 1
        if file_count % 50 == 0:
          print(f"  Added {file_count} files...")

  print(f"\n✓ Archive created: {ZIP_NAME} ({file_count} files)")


if __name__ == "__main__":
  print("=" * 50)
  print("Packing YACSP release")
  print("=" * 50)
  create_release()
  create_zip()
  print("\n" + "=" * 50)
  print("Done!")
  print("=" * 50)
