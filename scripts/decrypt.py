import argparse
import os
import sys
from pathlib import Path

try:
  from cryptography.fernet import Fernet
except ImportError:
  print("Error: cryptography is not installed.")
  sys.exit(1)

INTERNAL_KEY = b"1llKWQG0rSXJgyI5GLja7iAw_x215iyPEZFlw4qaTyI="


def decrypt_log(input_path: str, output_path: str = None):
  input_file = Path(input_path)

  if not input_file.exists():
    print(f"[!] File is not found: {input_path}")
    return

  cipher = Fernet(INTERNAL_KEY)
  decrypted_lines = []

  print(f"[*] Reading encrypted log: {input_path}")

  try:
    with open(input_file, "rb") as f:
      for _, line in enumerate(f, 1):
        line = line.strip()
        if not line:
          continue

        try:
          decoded = cipher.decrypt(line).decode("utf-8")
          decrypted_lines.append(decoded)
        except Exception:
          decrypted_lines.append(line.decode("utf-8"))  # provide as is

  except Exception as e:
    print(f"[!] Critical file reading error: {e}")
    return

  if output_path:
    try:
      with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(decrypted_lines))
      print(f"[+] Decrypted file saved to: {output_path}")
    except Exception as e:
      print(f"[!] Error: {e}")
  else:
    print("\n" + "=" * 50)
    print(" DECRYPTED LOG ")
    print("=" * 50 + "\n")
    print("\n".join(decrypted_lines))
    print("\n" + "=" * 50)


def main():
  parser = argparse.ArgumentParser(description="YACSP decryptor DO NOT DISTRIBUTE PLS.")
  parser.add_argument("file", help="Path to encrypted file")
  parser.add_argument(
    "-o",
    "--output",
    help="Output file (optional)",
  )

  args = parser.parse_args()
  decrypt_log(args.file, args.output)


if __name__ == "__main__":
  main()
