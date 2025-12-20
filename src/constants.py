import os
import sys
from core import utils

win_w = 360
win_h = 270

try:
  IS_COMPILED = __compiled__
except NameError:
  IS_COMPILED = getattr(sys, "frozen", False)

IS_DEV_MODE = not IS_COMPILED
CHECK_LICENSE = IS_COMPILED

PROJECT_ROOT = utils.get_project_root()
SANDBOX_PATH = os.path.join(PROJECT_ROOT, "data", "sandbox")
