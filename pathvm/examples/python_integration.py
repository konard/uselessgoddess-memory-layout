"""
Example: Python integration with PathVM

This example shows how to integrate PathVM with the existing Python codebase.
It demonstrates the migration path from the current walk.py implementation.
"""

# NOTE: This is example code showing the intended integration pattern.
# The actual pathvm module needs to be built with maturin first:
#   cd pathvm && maturin develop --release

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

# Simulated imports - replace with actual imports in production
if TYPE_CHECKING:
    import win32api
    import win32con


def execute_action_request(request: dict, delta: float) -> tuple[bool, str | None]:
    """
    Execute an action request from PathVM.

    This function bridges PathVM's action requests to the actual
    system calls (keyboard/mouse events).

    Args:
        request: Action request dict from PathVM.step()
        delta: Time delta for this frame

    Returns:
        (completed, team_change) tuple
    """
    action_type = request.get("type")
    completed = False
    team_change = None

    if action_type == "key_press":
        keys = request.get("keys", [])
        hold = request.get("hold", False)
        for vk_code in keys:
            # win32api.keybd_event(vk_code, 0, 0, 0)
            print(f"  [KEY] Press vk={hex(vk_code)}, hold={hold}")

    elif action_type == "key_release":
        keys = request.get("keys", [])
        for vk_code in keys:
            # win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
            print(f"  [KEY] Release vk={hex(vk_code)}")

    elif action_type == "mouse_press":
        flag = request.get("flag", 0)
        button = request.get("button", "left")
        # win32api.mouse_event(flag, 0, 0, 0, 0)
        print(f"  [MOUSE] Press {button}")

    elif action_type == "mouse_release":
        flag = request.get("flag", 0)
        button = request.get("button", "left")
        # win32api.mouse_event(flag, 0, 0, 0, 0)
        print(f"  [MOUSE] Release {button}")

    elif action_type == "mouse_move":
        dx = request.get("dx", 0)
        dy = request.get("dy", 0)
        # win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
        print(f"  [MOUSE] Move dx={dx:.2f}, dy={dy:.2f}")

    elif action_type == "rotate":
        target = request.get("target", 0)
        precision = request.get("precision", 5.0)
        max_angle = request.get("max_angle", 100.0)
        # This would call the rotation detection and smooth rotation logic
        print(f"  [ROTATE] target={target}, precision={precision}")
        # For now, mark as completed after one tick
        completed = True

    elif action_type == "change_team":
        team = request.get("team")
        team_change = team
        completed = True
        print(f"  [TEAM] Change to {team}")

    elif action_type == "buy":
        items = request.get("items", [])
        for item in items:
            cat = item.get("category")
            itm = item.get("item")
            # Press category key, then item key
            print(f"  [BUY] Category {cat}, Item {itm}")

    elif action_type == "weapon_slot":
        slot = request.get("slot", 1)
        print(f"  [WEAPON] Slot {slot}")

    elif action_type == "none":
        pass  # Do nothing

    return completed, team_change


def run_path_example():
    """Run a simple path execution example."""
    # Example YAML path
    yaml_content = """
name: "demo_path"
description: "Simple demonstration path"

path:
  - move:
      keys: [W, A]
    duration: 1.0

  - inspect:
      hold: false
    duration: 0.3

  - maybe:
      chance: 0.5
      then:
        - shoot:
            hold: false
          duration: 0.1

  - select:
      options:
        - - move:
              keys: [W]
            duration: 0.5
        - - move:
              keys: [S]
            duration: 0.5
"""

    print("=" * 60)
    print("PathVM Integration Example")
    print("=" * 60)

    try:
        # Try to import the actual module
        from pathvm import PathConfig, PathVM, Team

        config = PathConfig(yaml_content)
        print(f"\nLoaded path: {config.name}")
        print(f"Description: {config.description}")

        # Create VM
        vm = PathVM(
            config,
            team=Team.T,
            bomb=False,
            last=False,
            fast=False,
            no_buy=False
        )

        print(f"\nStarting execution (team={vm.team().label()})")
        print(f"Remaining edges: {vm.remaining_edges()}")
        print("-" * 40)

        # Simulate execution loop
        delta = 0.1
        step_count = 0
        max_steps = 100

        while not vm.is_completed() and step_count < max_steps:
            result = vm.step(delta)

            if result["requests"]:
                print(f"\nStep {step_count}:")
                for request in result["requests"]:
                    execute_action_request(request, delta)

            if result["team_change"]:
                print(f"\n>>> Team changed to: {result['team_change']}")

            step_count += 1
            time.sleep(0.01)  # Small delay for readability

        print("-" * 40)
        print(f"\nExecution completed after {step_count} steps")
        print(f"Final team: {vm.team().label()}")

    except ImportError as e:
        print(f"\nNote: pathvm module not built yet.")
        print(f"To build: cd pathvm && maturin develop --release")
        print(f"\nShowing what the execution would look like...\n")

        # Simulate what would happen
        print("Step 0:")
        print("  [KEY] Press vk=0x57 (W), hold=False")
        print("  [KEY] Press vk=0x41 (A), hold=False")
        print("\nStep 10:")
        print("  [KEY] Release vk=0x57 (W)")
        print("  [KEY] Release vk=0x41 (A)")
        print("\nStep 11:")
        print("  [KEY] Press vk=0x46 (F - inspect), hold=False")
        print("\n...")


def show_migration_example():
    """Show how to migrate from the old Python implementation."""
    print("\n" + "=" * 60)
    print("Migration Example: Old Python -> New YAML")
    print("=" * 60)

    print("""
BEFORE (Python - walk.py):
--------------------------

def left_killall():
    return [
        SetDirection(Path.RIGHT),
        (40.0, rotate(0, 5.0)),
        (3.0, [Key.W, Key.A]),
        (2.0, [Key.W, Key.D]),
        (3.0, [Key.W]),
        (0.5, [Key.S, Key.A]),
        maybe(
            recursive(
                lambda _: [
                    ChangeTeam(Team.T),
                    T.right_killall(),
                    Select([[], [], If(lambda ctx: not ctx.last, maybe(ChangeTeam()))])
                ]
            ),
            chance=0.25,
        ),
    ]

AFTER (YAML):
-------------

name: "t_left_killall"
map: "de_inferno"
mode: "scrimcomp2v2"
team: t

path:
  - set_direction:
      direction: right

  - rotate:
      target: 0
      precision: 5.0
    duration: 40.0

  - move:
      keys: [W, A]
    duration: 3.0

  - move:
      keys: [W, D]
    duration: 2.0

  - move:
      keys: [W]
    duration: 3.0

  - move:
      keys: [S, A]
    duration: 0.5

  - maybe:
      chance: 0.25
      then:
        - change_team:
            team: t
        - path_ref: "t_right_killall"
        - select:
            options:
              - []
              - []
              - if:
                  condition: not_last
                  then:
                    - maybe:
                        chance: 0.5
                        then:
                          - change_team: {}

BENEFITS:
---------
1. No Python knowledge required to create/edit paths
2. Paths can be shared as simple text files
3. Validation before execution
4. Better error messages
5. Performance (Rust execution)
6. Type safety
""")


if __name__ == "__main__":
    run_path_example()
    show_migration_example()
