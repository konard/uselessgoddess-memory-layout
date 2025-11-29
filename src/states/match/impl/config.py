from dataclasses import dataclass
from typing import Tuple


@dataclass
class Config:
  # Input resolution to the model (frame is resized to a square of this size)
  model_input: int = 320

  # TODO: use panel config
  screenshot_width = 360
  screenshot_height = 270

  # Autoaim mouse movement amplifier
  aa_movement_amp: float = 3.0

  # Person Class Confidence
  confidence: float = 0.0  # TODO: research

  # Chance to start headshot aim controller
  headshot_chance: float = 0.50

  # Prioritize targets closest to the screen center
  center_of_screen: bool = True

  # Filter out lying targets by aspect ratio: skip if width/height > this
  filter_aspect: float = 0.60

  # Shooting configuration
  shoot_distance_threshold: float = 35.0
  shoot_cooldown: Tuple[float] = 0.1, 0.3
  shoot_burst: Tuple[float] = 0.2, 0.5
  shoot_pistol: Tuple[float] = 0.1, 0.3

  # Rotation configuration
  enable_rotation: bool = True
  rotation_speed: float = 100.0
  rotation_interval: float = 3.0


config = Config()
