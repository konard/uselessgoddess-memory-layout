import random
import types

import win32api
import win32con
from typing import List, Tuple, Union
from abc import ABC, abstractmethod

from core.logging import get_logger
from core.keys import Key
from .rotation import rotate_step, smooth_rotate_to_target
from .detector import MinimapConfig, MinimapDirectionDetector
from .aim import AimController
from .utils import (
  Action,
  Context,
  Step,
  Team,
)

logger = get_logger("match.path")


def number(num: int) -> Key:
  return Key(Key._0.value + num)


def scancode(num: int) -> Key:
  return Key(Key._0.value + (num - 30 + 1))


class MoveAction(Action):
  def __init__(self, keys: List[Key], hold: bool = False):
    self.hold = hold
    self.keys = keys

  def execute(self, ctx: Context) -> Step:
    for key in self.keys:
      win32api.keybd_event(key.value, 0, 0, 0)
    return False, None

  def release(self):
    if not self.hold:
      for key in self.keys:
        win32api.keybd_event(key.value, 0, win32con.KEYEVENTF_KEYUP, 0)


class KeyAction(Action):
  def __init__(self, key: Key, hold: bool = False):
    self.hold = hold
    self.key = key

  def execute(self, ctx: Context) -> Step:
    win32api.keybd_event(self.key.value, 0, 0, 0)
    return False, None

  def release(self):
    if not self.hold:
      win32api.keybd_event(self.key.value, 0, win32con.KEYEVENTF_KEYUP, 0)


class NoneAction(Action):
  def execute(self, ctx: Context) -> Step:
    return False, None

  def release(self):
    pass


class MouseAction(Action):
  def __init__(self, button: int):
    self.button = button

  def execute(self, ctx: Context) -> Step:
    win32api.mouse_event(self.button, 0, 0, 0, 0)
    return False, None

  def release(self):
    release_button = self.button << 1
    win32api.mouse_event(release_button, 0, 0, 0, 0)


class MouseMove(Action):
  def __init__(self, x, y):
    self.x = x
    self.y = y

  def execute(self, ctx: Context) -> Step:
    win32api.mouse_event(
      win32con.MOUSEEVENTF_MOVE,
      int(-self.x * ctx.delta),
      int(-self.y * ctx.delta),
      0,
      0,
    )
    return False, None

  def release(self):
    pass


class RotateAction(Action):
  def __init__(
    self,
    target_rotation: float,
    precision: float = 5.0,
    max_angle: float = 100.0,
  ):
    self.target_rotation = target_rotation
    self.precision = precision
    self.max_angle = max_angle
    self.current_rotation = None
    self.detector = None

  def release(self):
    pass

  def execute(self, ctx: Context) -> Step:
    if self.detector is None:
      self.detector = MinimapDirectionDetector(MinimapConfig())

    current_rotation = self.detector.extract_rotation(ctx.frame, visuals=False)

    if current_rotation is not None:
      current_deg = current_rotation % 360
      target_deg = self.target_rotation % 360
      diff = (target_deg - current_deg + 360) % 360

      if abs(diff) <= self.precision or abs(diff - 360) <= self.precision:
        return True, None

      turn_magnitude = diff if diff <= 180 else 360 - diff

      if turn_magnitude > self.max_angle:
        return True, ctx.team  # god pls

      smooth_rotate_to_target(
        current_rotation, self.target_rotation, 10 * ctx.delta
      )
    else:
      rotate_step(100 * ctx.delta)

    return False, None


class ChangeTeam(Action):
  def __init__(self, team: Team = None):
    self.team = team

  def execute(self, ctx: Context) -> Step:
    if self.team is None:
      return True, ctx.team.enemy()
    else:
      return True, self.team

  def release(self):
    pass


Edge = Action | Tuple[float, Union[List[Key], Action]]


class Path:
  LEFT: int = -1
  RIGHT: int = 1

  def __init__(self, edges: List[Edge], team):
    self.edges = edges
    self.timer = 0
    self.team = team

  def step(
    self, frame, targets: List, delta: float
  ) -> Tuple[bool, Team | None]:
    if len(self.edges) == 0:
      return True, None

    if isinstance(self.edges[0], tuple):
      duration, action = self.edges[0]
    else:
      action = self.edges[0]
      duration = 0.25

    if isinstance(action, list):
      if self.timer >= duration:
        for key in action:
          win32api.keybd_event(key.value, 0, win32con.KEYEVENTF_KEYUP, 0)
        del self.edges[0]
        self.timer = 0
      else:
        self.timer += delta
        for key in action:
          win32api.keybd_event(key.value, 0, 0, 0)
      return False, None

    team = None

    ctx = Context(self.team, frame, targets, delta)
    release, change_team = action.execute(ctx)
    if change_team is not None:
      team = change_team
      self.team = team
    self.timer += delta

    if self.timer > duration or release:
      action.release()
      del self.edges[0]
      self.timer = 0

    return False, team


class BuilderContext:
  def __init__(self, team: Team, bomb: bool, last: bool):
    self.team = team
    self.bomb = bomb
    self.last = last
    self.burst = False
    self.grenade = False
    self.recursive = False
    self.direction = Path.LEFT


class ActionBuilder(ABC):
  @abstractmethod
  def build(self, ctx: BuilderContext) -> List[Edge]:
    pass


class AList(ActionBuilder):
  def __init__(self, actions: List[Edge]):
    self.actions = actions

  def build(self, _ctx: BuilderContext) -> List[Edge]:
    return self.actions


class Select(ActionBuilder):
  def __init__(self, actions: List):
    self.actions = actions

  def build(self, ctx: BuilderContext) -> List[Edge]:
    action = random.choice(self.actions)
    return extract(action, ctx)


class Maybe(ActionBuilder):
  def __init__(self, action, chance: float):
    self.action = action
    self.chance = chance

  def build(self, ctx: BuilderContext) -> List[Edge]:
    if random.random() < self.chance:
      return extract(self.action, ctx)
    else:
      return []


class If(ActionBuilder):
  def __init__(self, cond, then: List, _else=None):
    if _else is None:
      _else = []
    self.cond = cond
    self.then = then
    self._else = _else

  def build(self, ctx: BuilderContext) -> List[Edge]:
    if self.cond(ctx):
      return extract(self.then, ctx)
    else:
      return extract(self._else, ctx)


class SetDirection(ActionBuilder):
  def __init__(self, direction: int):
    self.direction = direction

  def build(self, ctx: BuilderContext) -> List[Edge]:
    ctx.direction = self.direction
    return []


class DisableRecursive(ActionBuilder):
  def __init__(self, recursive: bool):
    self.recursive = recursive

  def build(self, ctx: BuilderContext) -> List[Edge]:
    ctx.recursive = self.recursive
    return []


def buy(col, row):
  return [(0.5, [number(col)]), (0.5, [number(row)])]


class BuyRandom(ActionBuilder):
  forbid = [
    (4, 3),
    (4, 5),  # sniper
    (5, 2),  # smoke
  ]

  def build(self, ctx: BuilderContext) -> List[Edge]:
    actions = []
    amount = random.randint(0, 4)

    # buy kevlar/helmet
    if random.randint(0, 100) < 85:
      actions.extend(buy(1, 2))

    for _ in range(amount):  # prevent pistols from buying
      category = random.randint(2, 5)
      weapon = random.randint(2, 5)

      if (category, weapon) in self.forbid:
        continue
      if weapon == 5:
        ctx.grenade = True

      actions.extend(buy(category, weapon))

    actions.insert(0, [(0.5, [Key.B])])
    actions.append([(0.5, [Key.B])])

    return actions


# todo!> make decorator to wrap same builders
class RandomKnifeDecorator(ActionBuilder):
  def __init__(self, builder: ActionBuilder, ratio: float = 0.5):
    self.builder = builder
    self.ratio = ratio
    self.hold = True

  def build(self, ctx: BuilderContext) -> List[Edge]:
    actions = self.builder.build(ctx)
    actions.append(inspect(hold=False))

    samples = int(self.ratio * random.randint(0, len(actions) - 1))

    while samples > 0:
      index = random.randint(0, len(actions) - 1)

      if isinstance(actions[index], tuple):
        duration, action = actions[index]
        # todo!> use custom action for list of buttons
        if isinstance(action, list):
          samples -= 1
          actions.insert(index, inspect(hold=self.hold))
          self.hold = not self.hold
    return actions


def infer_path(
  name: str,
  mode: str,
  team: Team,
  bomb: bool,
  last_round: bool = False,
) -> Path | None:
  try:
    label = team.label()
    if bomb and not last_round:
      label = f"{label}.bomb"
    skel = static_paths()[name][mode][label]
  except KeyError:
    return None

  # apply decorators
  ctx = BuilderContext(team, bomb, last_round)
  skel = random.choice(skel)
  skel.insert(
    0,
    [
      BuyRandom(),
      wait(0.25),
      # avoid bomb dropshot
      (0.1, [Key.W]),
      (0.1, [Key.S]),
      wait(1.0),
    ],
  )
  skel.append(
    [
      weapon(1),  # always try to use primary weapon
      weapon(4),  # throw grenade if exists
    ]
  )

  skel = RandomKnifeDecorator(AList(skel)).build(ctx)
  path = Path(extract(skel, ctx), team)
  # final aim after walk (2 min limit)
  path.edges.append((120, AimController(ctx.direction, burst=ctx.burst)))

  for edge in path.edges:
    logger.trace(edge)

  return path


def shoot(duration: float = 0.1, hold: bool = False) -> Edge:
  return duration, KeyAction(Key.K, hold=hold)


def alt_shoot(duration: float = 0.1, hold: bool = False) -> Edge:
  return duration, KeyAction(Key.L, hold=hold)


def rotate(target_rotation: float, precision: float = 5.0) -> Action:
  return RotateAction(target_rotation, precision)


def inspect(hold: bool = False) -> Action:
  return KeyAction(Key.F, hold=hold)


def key(key: Key, hold: bool = False) -> Edge:
  if hold:
    return 0.25, KeyAction(key, hold=hold)
  else:
    return 0.25, [key]


def buy_smoke() -> Edge:
  return 0.25, key(scancode(35))


def weapon(slot: int, hold: bool = False):
  def inner(ctx: BuilderContext) -> Action:
    ctx.burst = slot == 1
    return key(number(slot), hold)

  return inner


def wait(duration: float) -> Edge:
  return duration, NoneAction()


def maybe(actions, chance: float = 0.5) -> Maybe:
  return Maybe(actions, chance)


def extract(layer, ctx: BuilderContext) -> List[Edge]:
  if isinstance(layer, list):
    actions = []
    for action in layer:
      actions.extend(extract(action, ctx))
    return actions
  elif isinstance(layer, ActionBuilder):
    return extract(layer.build(ctx), ctx)
  elif isinstance(layer, types.LambdaType):
    return extract(layer(ctx), ctx)
  elif isinstance(layer, Tuple):
    return [layer]
  elif isinstance(layer, Action):
    return [layer]

  logger.error(f"unsupported layer type: {type(layer)}")
  return []


def recursive(a, b=None):
  if b is None:
    b = []

  def inner(ctx: BuilderContext):
    if not ctx.recursive:
      ctx.recursive = True
      return a
    else:
      return b

  return inner


class T:
  @staticmethod
  def left_killall():
    return [
      SetDirection(Path.RIGHT),
      (40.0, rotate(0, 5.0)),
      (3.0, [Key.W, Key.A]),
      (2.0, [Key.W, Key.D]),
      (3.0, [Key.W]),
      (0.5, [Key.S, Key.A]),
      (3.0, [Key.A]),
      (0.5, [Key.S, Key.A]),
      (1.5, [Key.W]),
      (3.0, [Key.W, Key.D]),
      (2.4, [Key.W]),
      (0.6, [Key.S, Key.D]),
      # todo!> provide by `infer_path` automatically
      maybe(
        recursive(
          lambda _: [
            ChangeTeam(Team.T),
            T.right_killall(),
            Select(
              [
                [],
                [],
                If(
                  lambda ctx: not ctx.last,  # then
                  maybe(ChangeTeam()),
                ),
                # todo!> change controller
              ]
            ),
          ]
        ),
        chance=0.25,
      ),
    ]

  @staticmethod
  def right_killall():
    return [
      SetDirection(Path.LEFT),
      (40.0, rotate(0, 5.0)),
      (3.0, [Key.W, Key.A]),
      (6.0, [Key.W, Key.D]),
      (1.0, [Key.S]),
      (1.0, [Key.D]),
      (4.5, [Key.W]),
      (0.5, [Key.A]),
      maybe(
        recursive(
          lambda _: [
            ChangeTeam(Team.T),
            T.left_killall(),
            Select(
              [
                [],
                [],
                If(
                  lambda ctx: not ctx.last,  # then
                  maybe(ChangeTeam()),
                ),
                # todo!> change controller
              ]
            ),
          ]
        ),
        chance=0.25,
      ),
    ]

  @staticmethod
  def simple_plant():
    return [
      DisableRecursive(True),
      (40.0, rotate(0, 5.0)),
      (3.0, [Key.W, Key.A]),
      (6.0, [Key.W, Key.D]),
      (1.0, [Key.S]),
      (1.0, [Key.D]),
      (2.0, [Key.W]),
      # planting
      [
        weapon(5),
        shoot(hold=True),
        (3.0, [Key.W, Key.A]),
        wait(3.0),
        shoot(hold=False),
        (1.0, [Key.S]),
      ],
      # something after plant
      Select(
        [
          [ChangeTeam(Team.T), T.left_killall(), maybe(ChangeTeam())],
          [ChangeTeam(Team.CT), CT.default_defuse(), maybe(ChangeTeam())],
          [(2.0, [Key.W]), (0.8, [Key.A])],
        ]
      ),
    ]


class CT:
  @staticmethod
  def right_killall():
    return [
      SetDirection(Path.LEFT),
      (40.0, rotate(180, 5.0)),
      (0.5, [Key.W]),
      (1.0, [Key.D]),
      (0.5, [Key.S]),
      (1.0, [Key.D]),
      (0.5, [Key.W]),
      (3.0, [Key.D]),
      (2.0, [Key.W]),
      (6.0, [Key.W, Key.A]),
      (2.0, [Key.W, Key.A]),
      (1.0, [Key.W, Key.D]),
      (1.0, [Key.S, Key.D]),  # stuck in rat angle
      maybe(
        recursive(
          lambda _: [
            ChangeTeam(Team.CT),
            CT.left_killall(),
            If(
              lambda ctx: not ctx.last,  # then
              maybe(ChangeTeam()),
            ),
          ]
        ),
        chance=0.25,
      ),
    ]

  @staticmethod
  def left_killall():
    return [
      SetDirection(Path.RIGHT),
      (40.0, rotate(180, 5.0)),
      (0.5, [Key.W]),
      (1.0, [Key.A]),
      (0.5, [Key.S]),
      (3.0, [Key.S, Key.A]),
      (0.2, [Key.W, Key.A]),  # to avoid box stuck
      (2.5, [Key.W]),
      (1.5, [Key.W, Key.A]),
      (1.0, [Key.W, Key.D]),
      (3.0, [Key.W]),
      (1.5, [Key.D]),
      (1.5, [Key.W, Key.D]),
      (1.0, [Key.W, Key.A]),
      (0.5, [Key.W, Key.D]),
      maybe(
        recursive(
          lambda _: [
            ChangeTeam(Team.CT),
            CT.right_killall(),
            Select(
              [
                [],
                [],
                If(
                  lambda ctx: not ctx.last,  # then
                  maybe(ChangeTeam()),
                ),
                # todo!> change controller
              ]
            ),
          ]
        ),
        chance=0.25,
      ),
    ]

  @staticmethod
  def default_defuse():
    return [
      (40.0, rotate(180, 5.0)),
      (0.5, [Key.W]),
      (1.0, [Key.A]),
      (0.5, [Key.S]),
      (3.0, [Key.S, Key.A]),
      (1.25, [Key.W]),
      maybe(
        [
          shoot(),
          shoot(),
          shoot(),
          shoot(),
          shoot(),
          shoot(),
        ]
      ),
      # ninja defuse
      maybe(
        [
          key(scancode(36)),
          alt_shoot(),
          wait(0.5),
          alt_shoot(),
        ]
      ),
      (1.0, MouseMove(0, -1000)),
      # todo!> use list of keys
      key(Key.CTRL, hold=True),
      key(Key.E, hold=True),
      (0.5, [Key.W]),
      (3.0, [Key.W, Key.D]),
      Select(
        [
          [wait(10.0)],
          [wait(5.0)],
        ]
      ),
      key(Key.CTRL, hold=False),
      key(Key.E, hold=False),
      (1.0, MouseMove(0, +1000)),
      maybe(
        [
          shoot(),
          shoot(),
          shoot(),
          shoot(),
          shoot(),
          shoot(),
        ]
      ),
      (0.5, [Key.S]),
    ]


def static_paths():
  return {
    "de_inferno": {
      "scrimcomp2v2": {
        "t": [
          T.right_killall(),
          T.left_killall(),
        ],
        "t.bomb": [
          T.simple_plant(),
        ],
        "ct": [CT.right_killall(), CT.left_killall()],
      }
    }
  }
