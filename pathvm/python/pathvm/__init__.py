"""
PathVM - Portable Path Execution Engine

A Rust-based path execution engine with YAML/JSON configuration support.
Designed for non-programmers to create and share path configurations.

Example:
    >>> from pathvm import PathConfig, PathVM, Team
    >>> config = PathConfig.from_file("my_path.yaml")
    >>> vm = PathVM(config, team=Team.T)
    >>> while not vm.is_completed():
    ...     result = vm.step(delta_time)
    ...     for request in result.requests:
    ...         execute_action(request)
"""

from pathvm._pathvm import (
    PyPathVM as PathVM,
    PyPathConfig as PathConfig,
    PyTeam as Team,
    PyActionRequest as ActionRequest,
    load_path_from_yaml,
    load_path_from_json,
    validate_config,
)

__version__ = "0.1.0"
__all__ = [
    "PathVM",
    "PathConfig",
    "Team",
    "ActionRequest",
    "load_path_from_yaml",
    "load_path_from_json",
    "validate_config",
]
