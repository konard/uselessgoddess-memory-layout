from typing import List, Tuple
from core.account.model import RunningAccount
from core.services.settings import FarmMode
from states.types import PartySchema


def generate_party_schema(
  launched_accounts: List[RunningAccount], farm_mode: FarmMode
) -> Tuple[PartySchema, PartySchema]:
  launched_accounts = sorted(launched_accounts, key=lambda x: x.login)
  if farm_mode == FarmMode.TWO_BY_TWO:
    return [
      PartySchema(leader=launched_accounts[0], members=[launched_accounts[1]]),
      PartySchema(leader=launched_accounts[2], members=[launched_accounts[3]]),
    ]
  elif farm_mode == FarmMode.FIVE_BY_FIVE:
    return [
      PartySchema(
        leader=launched_accounts[0],
        members=[
          launched_accounts[1],
          launched_accounts[2],
          launched_accounts[3],
          launched_accounts[4],
        ],
      ),
      PartySchema(
        leader=launched_accounts[5],
        members=[
          launched_accounts[6],
          launched_accounts[7],
          launched_accounts[8],
          launched_accounts[9],
        ],
      ),
    ]
  else:
    raise ValueError(f"Invalid farm mode: {farm_mode}")
