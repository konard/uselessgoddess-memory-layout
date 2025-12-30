from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS_JSON_PATH = PROJECT_ROOT / "accounts.json"
MAFILES_DIR = PROJECT_ROOT / "data" / "maFiles"


def load_json_file(path: Path) -> dict | None:
  try:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)
  except Exception:
    return None


def build_mafile_indexes(
  mafiles_dir: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
  by_steamid: dict[str, str] = {}
  by_account_name: dict[str, str] = {}
  by_basename: dict[str, str] = {}

  if not mafiles_dir.exists():
    return by_steamid, by_account_name, by_basename

  for path in mafiles_dir.iterdir():
    if not path.is_file():
      continue
    name_lower = path.name.lower()
    if name_lower == "manifest.json":
      continue
    # Accept .maFile and .mafile (case-insensitive)
    if (
      not name_lower.endswith((".mafile", ".maFile"))
      # Allow any file that starts with .ma (rare cases), but skip others
      and ".ma" not in name_lower
    ):
      continue

    data = load_json_file(path)
    if not isinstance(data, dict):
      continue

    identity_secret = data.get("identity_secret")
    if not identity_secret:
      continue

    steamid = data.get("SteamID") or data.get("steamid") or data.get("steam_id")
    if steamid is not None:
      by_steamid[str(steamid)] = identity_secret

    account_name = (
      data.get("account_name") or data.get("accountName") or data.get("login")
    )
    if isinstance(account_name, str) and account_name:
      by_account_name[account_name.lower()] = identity_secret

    basename = path.stem
    if basename:
      by_basename[basename.lower()] = identity_secret

  return by_steamid, by_account_name, by_basename


def find_identity_secret(
  login: str | None,
  steam_id: int | None,
  idx_steamid: dict[str, str],
  idx_account: dict[str, str],
  idx_basename: dict[str, str],
) -> str | None:
  # Prefer exact steamid match
  if steam_id is not None:
    v = idx_steamid.get(str(steam_id))
    if v:
      return v
  # Then account name from content
  if login:
    v = idx_account.get(login.lower())
    if v:
      return v
    # Then by filename base
    v = idx_basename.get(login.lower())
    if v:
      return v
  # Finally, if steam_id provided, try by filename base as string
  if steam_id is not None:
    v = idx_basename.get(str(steam_id).lower())
    if v:
      return v
  return None


def update_accounts(accounts_path: Path, target: str | None = None) -> int:
  accounts = load_json_file(accounts_path)
  if not isinstance(accounts, dict):
    raise SystemExit(f"Не удалось прочитать JSON: {accounts_path}")

  idx_steamid, idx_account, idx_basename = build_mafile_indexes(MAFILES_DIR)

  # Determine filter predicate
  target_is_steamid = None
  target_norm = None
  if target:
    target_norm = target.strip()
    target_is_steamid = target_norm.isdigit()

  updated_count = 0
  for key, account in accounts.items():
    if not isinstance(account, dict):
      continue

    login = account.get("login") or key
    steam_id = account.get("steam_id")

    if target_norm:
      if target_is_steamid:
        if str(steam_id) != target_norm:
          continue
      else:
        if str(login).lower() != target_norm.lower():
          continue

    identity_secret = find_identity_secret(
      login, steam_id, idx_steamid, idx_account, idx_basename
    )
    if identity_secret and account.get("identity_secret") != identity_secret:
      account["identity_secret"] = identity_secret
      updated_count += 1

  # Persist only if any change
  if updated_count > 0:
    # Keep order; pretty-print with 4 spaces to match existing style
    accounts_path.write_text(
      json.dumps(accounts, ensure_ascii=False, indent=4) + "\n",
      encoding="utf-8",
    )

  return updated_count


def main(argv: list[str]) -> int:
  if not ACCOUNTS_JSON_PATH.exists():
    print(f"Файл не найден: {ACCOUNTS_JSON_PATH}")
    return 2
  if not MAFILES_DIR.exists():
    print(f"Папка с maFile не найдена: {MAFILES_DIR}")
    return 2

  target: str | None = None
  if len(argv) >= 2:
    target = argv[1]

  updated = update_accounts(ACCOUNTS_JSON_PATH, target)
  if target:
    print(f"Обновлено записей: {updated} (фильтр: {target})")
  else:
    print(f"Обновлено записей: {updated}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv))
