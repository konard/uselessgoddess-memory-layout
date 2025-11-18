import asyncio
import json
import urllib.request
import win32com.client
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from icmplib import async_ping

from core.logging import get_logger

logger = get_logger("sv.sdr")

SDR_CONFIG_URL = (
  "https://api.steampowered.com/ISteamApps/GetSDRConfig/v1?appid=730"
)
# TODO: make local backup
SDR_CONFIG_BACKUP = "https://raw.githubusercontent.com/SteamDatabase/SteamTracking/597d81b2a436d260a7ffe3b53eb3b9ed932c2efb/Random/NetworkDatagramConfig.json"

NET_FW_RULE_DIR_OUT = 2
NET_FW_ACTION_BLOCK = 0
NET_FW_IP_PROTOCOL_UDP = 17


@dataclass
class Relay:
  ipv4: str
  port_range: List[int]


@dataclass
class Route:
  name: str
  desc: str
  relays: List[Relay]
  ping: int = -1
  blocked: bool = False

  @property
  def display_name(self) -> str:
    return self.desc if self.desc else self.name


class SRTService:
  def __init__(self):
    self.routes: List[Route] = []
    self._fw_policy = None

  def load_routes(self) -> List[Route]:
    logger.debug("load srt routes")

    data = None
    try:
      with urllib.request.urlopen(SDR_CONFIG_URL, timeout=5) as response:
        data = json.loads(response.read().decode())
    except Exception:
      logger.warn(
        "Failed to fetch SDR config from primary URL, trying backup..."
      )
      try:
        with urllib.request.urlopen(SDR_CONFIG_BACKUP, timeout=5) as response:
          data = json.loads(response.read().decode())
      except Exception as e:
        logger.error(f"Failed to fetch SDR config: {e}")
        return []

    self.routes = []
    if not data or "pops" not in data:
      return []

    for name, info in data["pops"].items():
      if "relays" not in info or "cloud-test" in str(info):
        continue

      relays = []
      for r in info["relays"]:
        relays.append(Relay(ipv4=r["ipv4"], port_range=r["port_range"]))

      route = Route(
        name=name,
        desc=info.get("desc", name),
        relays=relays,
      )
      self.routes.append(route)

    self._sync_blocked_status()
    return self.routes

  def _get_fw_policy(self):
    if not self._fw_policy:
      try:
        self._fw_policy = win32com.client.Dispatch("HNetCfg.FwPolicy2")
      except Exception as e:
        logger.error(f"Failed to initialize Firewall Policy: {e}")
    return self._fw_policy

  def _sync_blocked_status(self):
    policy = self._get_fw_policy()
    if not policy:
      return

    blocked_names = set()
    for rule in policy.Rules:
      if rule.Name.startswith("SteamRouteTool-"):
        route_name = rule.Name.split("-", 1)[1]
        blocked_names.add(route_name)

    for route in self.routes:
      route.blocked = route.name in blocked_names

  async def ping_all(self):
    semaphore = asyncio.Semaphore(50)

    async def protected_ping(route):
      async with semaphore:
        await self._ping_route(route)

    tasks = [protected_ping(route) for route in self.routes]
    await asyncio.gather(*tasks)

  async def _ping_route(self, route: Route):
    if not route.relays:
      return

    target_ip = route.relays[0].ipv4

    try:
      host = await async_ping(
        target_ip,
        count=1,
        timeout=2,
        privileged=True,
      )

      if host.is_alive:
        route.ping = int(host.avg_rtt)
      else:
        route.ping = 999  # Timeout

    except Exception as e:
      logger.trace(f"Ping failed for {route.name}: {e}")
      route.ping = -1

  def toggle_route(self, route_name: str, block: bool):
    route = next((r for r in self.routes if r.name == route_name), None)
    if not route:
      return

    policy = self._get_fw_policy()
    if not policy:
      return

    rule_name = f"SteamRouteTool-{route.name}"

    try:
      policy.Rules.Remove(rule_name)
    except Exception:
      pass

    if block:
      try:
        rule = win32com.client.Dispatch("HNetCfg.FWRule")
        rule.Name = rule_name
        rule.Description = f"Block access to Steam Region {route.desc}"
        rule.Protocol = NET_FW_IP_PROTOCOL_UDP
        rule.Direction = NET_FW_RULE_DIR_OUT
        rule.Action = NET_FW_ACTION_BLOCK
        rule.Enabled = True

        remote_addresses = []

        min_port = 99999
        max_port = 0

        for relay in route.relays:
          remote_addresses.append(relay.ipv4)

          p_start = int(relay.port_range[0])
          p_end = int(relay.port_range[1])

          if p_start < min_port:
            min_port = p_start
          if p_end > max_port:
            max_port = p_end

        rule.RemoteAddresses = ",".join(remote_addresses)
        rule.RemotePorts = f"{min_port}-{max_port}"

        policy.Rules.Add(rule)
        route.blocked = True
        logger.info(f"Blocked route: {route.name}")
      except Exception as e:
        logger.error(f"Failed to create firewall rule for {route.name}: {e}")
    else:
      route.blocked = False
      logger.info(f"Unblocked route: {route.name}")

  def clear_all_rules(self):
    policy = self._get_fw_policy()
    if not policy:
      return

    to_remove = []
    for rule in policy.Rules:
      if rule.Name.startswith("SteamRouteTool-"):
        to_remove.append(rule.Name)

    for name in to_remove:
      try:
        policy.Rules.Remove(name)
      except Exception:
        pass

    for route in self.routes:
      route.blocked = False

    logger.info(f"Cleared {len(to_remove)} rules.")
