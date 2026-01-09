# PathVM - Portable Path Execution Engine

A Rust-based path execution engine with YAML/JSON configuration support, designed for non-programmers to create and share path configurations.

## Features

- **YAML/JSON Configuration**: Human-readable path definitions
- **Behavior Tree-like Structure**: Supports complex decision trees
- **Chaos Features**: Random selection, probability-based execution, conditions
- **Python Integration**: PyO3 bindings for seamless integration
- **Type Safety**: Rust's compile-time guarantees

## Installation

### Building from Source

```bash
cd pathvm
pip install maturin
maturin develop --release
```

### Using in Python

```python
import pathvm

# Load configuration
config = pathvm.PyPathConfig.from_file("path.yaml")

# Create VM
vm = pathvm.PyPathVM(
    config,
    team=pathvm.PyTeam.T,
    bomb=False,
    last=False,
    fast=False,
    no_buy=False
)

# Execute path
while not vm.is_completed():
    result = vm.step(delta_time)
    for request in result["requests"]:
        execute_action(request)  # Your implementation
```

## Configuration Format

### Basic Structure

```yaml
name: "my_path"
map: "de_inferno"          # Optional: target map
mode: "scrimcomp2v2"        # Optional: game mode
team: t                     # Optional: t or ct
requires_bomb: false        # Optional: requires bomb carrier
description: "My path"      # Optional: documentation

path:
  - <action>
  - <action>
  ...
```

### Actions

#### Movement

```yaml
# Move with multiple keys
- move:
    keys: [W, A]           # W, A, S, D, Shift, Ctrl
    hold: false            # Keep keys held after duration
  duration: 2.0            # Seconds

# Single key press
- key:
    key: F                 # Any supported key
    hold: false
  duration: 0.5
```

#### Mouse

```yaml
# Mouse click
- mouse:
    button: left           # left, right, middle
  duration: 0.1

# Mouse movement
- mouse_move:
    x: 100                 # Relative X movement
    y: 0                   # Relative Y movement
  duration: 0.5
```

#### Combat

```yaml
# Shoot (K key)
- shoot:
    hold: false
  duration: 0.1

# Alt shoot (L key)
- alt_shoot:
    hold: false
  duration: 0.1

# Weapon slot
- weapon:
    slot: 1               # 1-5
```

#### Rotation

```yaml
- rotate:
    target: 180           # Target angle (degrees)
    precision: 5.0        # Acceptable error
    max_angle: 100.0      # Max turn per step
  duration: 40.0
```

#### Team & Utility

```yaml
# Change team
- change_team:
    team: ct              # t, ct, or omit for enemy team

# Buy random items
- buy_random: {}

# Wait
- wait: {}
  duration: 1.0

# Inspect weapon
- inspect:
    hold: false
  duration: 0.5
```

### Builders (Chaos Features)

#### Random Selection

```yaml
- select:
    options:
      - - move: { keys: [W] }
          duration: 1.0
      - - move: { keys: [S] }
          duration: 1.0
      - []  # Empty option (do nothing)
```

#### Probability-Based Execution

```yaml
- maybe:
    chance: 0.5           # 50% chance
    then:
      - shoot: { hold: false }
        duration: 0.1
```

#### Conditional Execution

```yaml
- if:
    condition: has_bomb
    then:
      - move: { keys: [W, A] }
        duration: 2.0
    else:
      - move: { keys: [W, D] }
        duration: 2.0
```

Available conditions:
- `not_last` / `is_last`: Check if last round
- `has_bomb` / `no_bomb`: Check bomb carrier
- `is_team: { team: t }`: Check team
- `not_recursive` / `is_recursive`: Check recursion flag
- `is_direction: { direction: left }`: Check direction
- `and: { conditions: [...] }`: All must be true
- `or: { conditions: [...] }`: Any must be true
- `not: { condition: ... }`: Negation
- `always` / `never`: Constant values

#### Direction Control

```yaml
- set_direction:
    direction: left       # left or right
```

#### Recursive Paths

```yaml
- recursive:
    primary:
      - move: { keys: [W] }
        duration: 1.0
    fallback:
      - move: { keys: [S] }
        duration: 1.0
```

## Python API Reference

### Classes

#### `PyTeam`
```python
PyTeam.T        # Terrorist
PyTeam.CT       # Counter-Terrorist

team.enemy()    # Get enemy team
team.label()    # Get string label ("t" or "ct")
```

#### `PyPathConfig`
```python
config = PyPathConfig(yaml_string)
config = PyPathConfig.from_file("path.yaml")

config.name           # Path name
config.map            # Target map (optional)
config.mode           # Game mode (optional)
config.team           # Target team (optional)
config.requires_bomb  # Whether bomb is required
config.description    # Documentation

config.validate()     # Validate configuration
```

#### `PyPathVM`
```python
vm = PyPathVM(config, team, bomb, last, fast, no_buy)
vm = PyPathVM.from_yaml(yaml_string, team, bomb, last, fast, no_buy)
vm = PyPathVM.from_file("path.yaml", team, bomb, last, fast, no_buy)

vm.step(delta)        # Step forward, returns dict
vm.team()             # Current team
vm.is_completed()     # Check if path finished
vm.remaining_edges()  # Remaining action count
vm.direction()        # Current direction (-1 or 1)
```

### Functions

```python
pathvm.load_path_from_yaml(yaml_string)  # -> PyPathConfig
pathvm.load_path_from_json(json_string)  # -> PyPathConfig
pathvm.validate_config(config)           # Validates configuration
```

## Migration from Python

### Before (Python)

```python
def left_killall():
    return [
        SetDirection(Path.RIGHT),
        (40.0, rotate(0, 5.0)),
        (3.0, [Key.W, Key.A]),
        (2.0, [Key.W, Key.D]),
        maybe(recursive(...), chance=0.25),
    ]
```

### After (YAML)

```yaml
name: "left_killall"
path:
  - set_direction: { direction: right }
  - rotate: { target: 0, precision: 5.0 }
    duration: 40.0
  - move: { keys: [W, A] }
    duration: 3.0
  - move: { keys: [W, D] }
    duration: 2.0
  - maybe:
      chance: 0.25
      then:
        - recursive:
            primary: [...]
```

## Supported Keys

| Key | Description |
|-----|-------------|
| W, A, S, D | Movement |
| Shift, Ctrl | Modifiers |
| E, F, B, K, L | Actions |
| 0-9 | Number keys |
| F3, Esc | Special keys |

## License

MIT
