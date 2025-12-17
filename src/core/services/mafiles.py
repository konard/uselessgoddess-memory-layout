from pathlib import Path
import json

from core.account.model import Account


class MafilesService:
  def __init__(self):
    self.mafiles = {}

  @staticmethod
  def _find_mafile_data(login: str) -> dict | None:
    """Поиск данных из mafile по login в директории data/mafiles."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[3]

    for dir_name in ["mafiles", "maFiles"]:
      mafiles_dir = project_root / "data" / dir_name
      if not mafiles_dir.exists():
        continue

      for ext in [".mafile", ".maFile"]:
        mafile_path = mafiles_dir / f"{login}{ext}"

      for mafile_path in mafiles_dir.iterdir():
        if not mafile_path.is_file():
          continue
        name_lower = mafile_path.name.lower()
        if name_lower == "manifest.json" or not (
          name_lower.endswith(".mafile") or ".ma" in name_lower
        ):
          continue

        try:
          with mafile_path.open("r", encoding="utf-8") as f:
            mafile_data = json.load(f)
          if not isinstance(mafile_data, dict):
            continue

          account_name = (
            mafile_data.get("account_name")
            or mafile_data.get("accountName")
            or mafile_data.get("login")
          )
          if (
            isinstance(account_name, str)
            and account_name.lower() == login.lower()
          ):
            return {
              "shared_secret": mafile_data.get("shared_secret"),
              "identity_secret": mafile_data.get("identity_secret"),
              "steam_id": mafile_data.get("Session", {}).get("SteamID"),
              "session": mafile_data.get("Session"),
            }
        except Exception:
          continue

    return None

  @staticmethod
  def _restore_from_mafile(data: dict) -> None:
    """Восстанавливает недостающие поля из mafile."""
    login = data.get("login")
    if not login:
      return

    # Проверяем, нужны ли восстановления
    needs_steam_id = "steam_id" not in data or not data["steam_id"]
    needs_shared_secret = (
      "shared_secret" not in data or not data["shared_secret"]
    )
    needs_identity_secret = (
      "identity_secret" not in data or not data["identity_secret"]
    )

    if not (needs_steam_id or needs_shared_secret or needs_identity_secret):
      return

    mafile_data = Account._find_mafile_data(login)
    if not mafile_data:
      return

    # Восстанавливаем steam_id
    if needs_steam_id:
      steam_id = (
        mafile_data.get("SteamID")
        or mafile_data.get("steamid")
        or mafile_data.get("steam_id")
        or (mafile_data.get("Session") or {}).get("SteamID")
      )
      if steam_id:
        data["steam_id"] = str(steam_id)

    # Восстанавливаем shared_secret
    if needs_shared_secret:
      shared_secret = mafile_data.get("shared_secret")
      if shared_secret:
        data["shared_secret"] = shared_secret

    # Восстанавливаем identity_secret
    if needs_identity_secret:
      identity_secret = mafile_data.get("identity_secret")
      if identity_secret:
        data["identity_secret"] = identity_secret
