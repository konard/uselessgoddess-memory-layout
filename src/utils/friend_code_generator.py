import hashlib

alnum = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ralnum = {c: i for i, c in enumerate(alnum)}


def b32(n):
  n = int.from_bytes(n.to_bytes(8, "little"), "big")
  res = ""
  for i in range(13):
    if i in (4, 9):
      res += "-"
    res += alnum[n & 0x1F]
    n >>= 5
  return res


def rb32(s):
  n = 0
  for i in range(13):
    if i in (4, 9):
      s = s[1:]
    n |= ralnum[s[0]] << (5 * i)
    s = s[1:]
  return int.from_bytes(n.to_bytes(8, "big"), "little")


def hash_steam_id(id):
  account_id = id & 0xFFFFFFFF
  strange_steam_id = account_id | 0x4353474F00000000
  h = hashlib.md5(strange_steam_id.to_bytes(8, "little")).digest()[:4]
  return int.from_bytes(h, "little")


def generate_friend_code(steamid):
  steamid = int(steamid)
  h = hash_steam_id(steamid)
  r = 0
  for i in range(8):
    id_nibble = steamid & 0xF
    steamid >>= 4
    hash_nibble = (h >> i) & 1
    a = (r << 4) | id_nibble
    r = ((r >> 28) << 32) | a
    r = ((r >> 31) << 32) | ((a << 1) | hash_nibble)
  res = b32(r)
  return res[5:] if res.startswith("AAAA-") else res
