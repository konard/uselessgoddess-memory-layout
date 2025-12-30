import base64
import json
import time


def is_jwt_valid(token: str) -> bool:
  try:
    parts = token.split(".")
    if len(parts) != 3:
      return False
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload))
    return data.get("exp", 0) > (time.time() + 300)
  except Exception:
    return False
