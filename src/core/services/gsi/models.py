from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, Optional


class Team(StrEnum):
  T = "T"
  CT = "CT"
  UNDEFINED = "undefined"

  def label(self):
    match self:
      case Team.T:
        return "t"
      case Team.CT:
        return "ct"
    return None

  def enemy(self):
    match self:
      case Team.T:
        return Team.CT
      case Team.CT:
        return Team.T
    return None


class MapPhase(StrEnum):
  LIVE = "live"
  WARMUP = "warmup"
  INTERMISSION = "intermission"
  GAME_OVER = "gameover"
  UNDEFINED = "undefined"


class RoundPhase(StrEnum):
  FREEZETIME = "freezetime"
  LIVE = "live"
  OVER = "over"
  UNDEFINED = "undefined"


class BombState(StrEnum):
  CARRIED = "carried"
  DROPPED = "dropped"
  PLANTING = "planting"
  PLANTED = "planted"
  DEFUSING = "defusing"
  DEFUSED = "defused"
  EXPLODED = "exploded"
  UNDEFINED = "undefined"


class PlayerActivity(StrEnum):
  MENU = "menu"
  PLAYING = "playing"
  TEXTINPUT = "textinput"
  UNDEFINED = "undefined"


class WeaponType(StrEnum):
  KNIFE = "Knife"
  PISTOL = "Pistol"
  RIFLE = "Rifle"
  SNIPER = "SniperRifle"
  SHOTGUN = "Shotgun"
  SMG = "Submachine Gun"
  MACHINEGUN = "Machine Gun"
  GRENADE = "Grenade"
  C4 = "C4"
  UNDEFINED = "undefined"


class WeaponState(StrEnum):
  HOLSTERED = "holstered"
  ACTIVE = "active"
  RELOADING = "reloading"
  UNDEFINED = "undefined"


# --- Data Classes ---


@dataclass
class Auth:
  token: str = ""


@dataclass
class Provider:
  name: str = ""
  appid: int = 0
  version: int = 0
  steamid: str = ""
  timestamp: int = 0


@dataclass
class Weapon:
  name: str = ""
  paintkit: str = ""
  type: WeaponType = WeaponType.UNDEFINED
  ammo_clip: int = 0
  ammo_clip_max: int = 0
  ammo_reserve: int = 0
  state: WeaponState = WeaponState.UNDEFINED


@dataclass
class PlayerStateData:
  health: int = 0
  armor: int = 0
  helmet: bool = False
  defusekit: bool = False
  flashed: int = 0
  smoked: int = 0
  burning: int = 0
  money: int = 0
  round_kills: int = 0
  round_killhs: int = 0
  round_totaldmg: int = 0
  equip_value: int = 0


@dataclass
class MatchStats:
  kills: int = 0
  assists: int = 0
  deaths: int = 0
  mvps: int = 0
  score: int = 0


@dataclass
class Player:
  steam_id: str = ""
  name: str = ""
  clan: str = ""
  observer_slot: int = 0
  team: Team = Team.UNDEFINED
  activity: PlayerActivity = PlayerActivity.UNDEFINED
  state: PlayerStateData = field(default_factory=PlayerStateData)
  weapons: list[Weapon] = field(default_factory=list)
  match_stats: MatchStats = field(default_factory=MatchStats)
  spectation_target: str = ""

  @property
  def active_weapon(self) -> Weapon | None:
    for w in self.weapons:
      if w.state == WeaponState.ACTIVE:
        return w
    return None


@dataclass
class Round:
  phase: RoundPhase = RoundPhase.UNDEFINED
  bomb_state: BombState = BombState.UNDEFINED
  win_team: Team = Team.UNDEFINED


@dataclass
class TeamStats:
  score: int = 0
  name: str = ""
  consecutive_round_losses: int = 0
  timeouts_remaining: int = 0
  matches_won_this_series: int = 0


@dataclass
class Map:
  mode: str = ""
  name: str = ""
  phase: MapPhase = MapPhase.UNDEFINED
  round: int = 0
  team_ct: TeamStats = field(default_factory=TeamStats)
  team_t: TeamStats = field(default_factory=TeamStats)
  num_matches_to_win_series: int = 0


@dataclass
class GameState:
  auth: Auth = field(default_factory=Auth)
  provider: Provider = field(default_factory=Provider)
  map: Map = field(default_factory=Map)
  round: Round = field(default_factory=Round)
  player: Player = field(default_factory=Player)

  # Raw handling helper
  @staticmethod
  def _parse_weapons(data: dict | list) -> list[Weapon]:
    weapons = []
    if isinstance(data, dict):
      # CS2 GSI returns weapons as Dict often {"weapon_0": {...}, "weapon_1": ...}
      # We sort them by index key to maintain order roughly
      sorted_items = sorted(data.items(), key=lambda x: x[0])
      for _, w_data in sorted_items:
        weapons.append(GameState._map_weapon(w_data))
    elif isinstance(data, list):
      for w_data in data:
        weapons.append(GameState._map_weapon(w_data))
    return weapons

  @staticmethod
  def _map_weapon(data: dict) -> Weapon:
    return Weapon(
      name=data.get("name", ""),
      paintkit=data.get("paintkit", ""),
      type=WeaponType(data.get("type", "undefined")),
      ammo_clip=data.get("ammo_clip", 0),
      ammo_clip_max=data.get("ammo_clip_max", 0),
      ammo_reserve=data.get("ammo_reserve", 0),
      state=WeaponState(data.get("state", "undefined")),
    )

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> GameState:
    # Auth & Provider
    auth = Auth(**data.get("auth", {}))
    prov_d = data.get("provider", {})
    provider = Provider(
      name=prov_d.get("name", ""),
      appid=prov_d.get("appid", 0),
      version=prov_d.get("version", 0),
      steamid=prov_d.get("steamid", ""),
      timestamp=prov_d.get("timestamp", 0),
    )

    # Map
    map_d = data.get("map", {})
    map_obj = Map(
      mode=map_d.get("mode", ""),
      name=map_d.get("name", ""),
      phase=MapPhase(map_d.get("phase", "undefined")),
      round=map_d.get("round", 0),
      team_ct=TeamStats(**map_d.get("team_ct", {})),
      team_t=TeamStats(**map_d.get("team_t", {})),
      num_matches_to_win_series=map_d.get("num_matches_to_win_series", 0),
    )

    # Round
    rnd_d = data.get("round", {})
    round_obj = Round(
      phase=RoundPhase(rnd_d.get("phase", "undefined")),
      bomb_state=BombState(rnd_d.get("bomb", "undefined")),
      win_team=Team(rnd_d.get("win_team", "undefined")),
    )

    # Player
    plr_d = data.get("player", {})
    player_obj = Player(
      steam_id=plr_d.get("steamid", ""),
      name=plr_d.get("name", ""),
      clan=plr_d.get("clan", ""),
      observer_slot=plr_d.get("observer_slot", 0),
      team=Team(plr_d.get("team", "undefined")),
      activity=PlayerActivity(plr_d.get("activity", "undefined")),
      state=PlayerStateData(**plr_d.get("state", {})),
      match_stats=MatchStats(**plr_d.get("match_stats", {})),
      weapons=cls._parse_weapons(plr_d.get("weapons", {})),
      spectation_target=plr_d.get("spectation_target", ""),
    )

    return cls(
      auth=auth,
      provider=provider,
      map=map_obj,
      round=round_obj,
      player=player_obj,
    )
