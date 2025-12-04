import os
import sys

RESOURCES_DIR = "resources"
OUTPUT_FILE = "src/resources.py"


def get_all_files(directory):
  file_paths = []
  for root, _, files in os.walk(directory):
    for filename in files:
      filepath = os.path.join(root, filename)
      file_paths.append(filepath)
  return file_paths


def draw_progress_bar(current, total, bar_length=40):
  percent = float(current) * 100 / total
  arrow = "#" * int(percent / 100 * bar_length)
  spaces = "." * (bar_length - len(arrow))

  sys.stdout.write(
    f"\rPacking: [{arrow}{spaces}] {int(percent)}% ({current}/{total})"
  )
  sys.stdout.flush()


def generate_resource_module():
  if not os.path.exists(RESOURCES_DIR):
    print(f"Error: Folder '{RESOURCES_DIR}' is not found.")
    return

  files = get_all_files(RESOURCES_DIR)
  total_files = len(files)

  if total_files == 0:
    print("Warning: Folder is empty.")
    return

  print(f"Found: {total_files}. Start packing to {OUTPUT_FILE}...")

  with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    out.write("# AUTO-GENERATED FILE. DO NOT EDIT.\n")
    out.write("_DATA = {}\n\n")

    for i, filepath in enumerate(files):
      rel_path = os.path.relpath(filepath, RESOURCES_DIR).replace("\\", "/")

      with open(filepath, "rb") as f:
        content = f.read()

      out.write(f'_DATA["{rel_path}"] = {repr(content)}\n')

      draw_progress_bar(i + 1, total_files)

    out.write("\n\n")
    out.write("def load(path: str) -> bytes:\n")
    out.write("    try:\n")
    out.write("        return _DATA[path]\n")
    out.write("    except KeyError:\n")
    out.write(
      "        raise FileNotFoundError(f'Embedded resource not found: {path}')\n"
    )

    out.write("\n")
    out.write("def list_files() -> list:\n")
    out.write("    return list(_DATA.keys())\n")

  print(f"\nDone! Resource file generated: {OUTPUT_FILE}")


if __name__ == "__main__":
  generate_resource_module()
