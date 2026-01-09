//! Configuration loading and validation
//!
//! This module handles loading path configurations from YAML/JSON files
//! and validating them before use.

use std::collections::HashMap;
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::action::{EdgeDef, Team};
use crate::builder::{extract_all, BuilderContext, PathNode};
use crate::error::PathError;
use crate::path::PathVM;

/// Top-level path configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PathConfig {
    /// Path name/identifier
    pub name: String,
    /// Target map (e.g., "de_inferno")
    #[serde(default)]
    pub map: Option<String>,
    /// Game mode (e.g., "scrimcomp2v2")
    #[serde(default)]
    pub mode: Option<String>,
    /// Target team
    #[serde(default)]
    pub team: Option<Team>,
    /// Whether this path requires bomb
    #[serde(default)]
    pub requires_bomb: bool,
    /// Description for documentation
    #[serde(default)]
    pub description: Option<String>,
    /// The path nodes
    pub path: Vec<PathNode>,
}

impl PathConfig {
    /// Load from YAML string
    pub fn from_yaml(yaml: &str) -> Result<Self, PathError> {
        serde_yaml::from_str(yaml).map_err(PathError::from)
    }

    /// Load from JSON string
    pub fn from_json(json: &str) -> Result<Self, PathError> {
        serde_json::from_str(json).map_err(PathError::from)
    }

    /// Load from file (auto-detects format)
    pub fn from_file<P: AsRef<Path>>(path: P) -> Result<Self, PathError> {
        let content = std::fs::read_to_string(&path)?;
        let path_str = path.as_ref().to_string_lossy();

        if path_str.ends_with(".yaml") || path_str.ends_with(".yml") {
            Self::from_yaml(&content)
        } else if path_str.ends_with(".json") {
            Self::from_json(&content)
        } else {
            // Try YAML first, then JSON
            Self::from_yaml(&content).or_else(|_| Self::from_json(&content))
        }
    }

    /// Build edges from this configuration
    pub fn build(&self, ctx: &mut BuilderContext) -> Result<Vec<EdgeDef>, PathError> {
        extract_all(&self.path, ctx)
    }

    /// Create a PathVM from this configuration
    pub fn create_vm(
        &self,
        team: Team,
        bomb: bool,
        last: bool,
        fast: bool,
        no_buy: bool,
    ) -> Result<PathVM, PathError> {
        let mut ctx = BuilderContext::new(team, bomb, last, fast, no_buy);
        let edges = self.build(&mut ctx)?;
        Ok(PathVM::new(edges, team))
    }
}

/// Path library - a collection of path configurations indexed by map/mode/team
#[derive(Debug, Default, Clone)]
pub struct PathLibrary {
    /// Paths indexed by: map -> mode -> team_label -> configs
    paths: HashMap<String, HashMap<String, HashMap<String, Vec<PathConfig>>>>,
}

impl PathLibrary {
    pub fn new() -> Self {
        Self::default()
    }

    /// Load all path configurations from a directory
    pub fn load_directory<P: AsRef<Path>>(&mut self, dir: P) -> Result<usize, PathError> {
        let mut count = 0;

        for entry in std::fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();

            if path.is_file() {
                let ext = path.extension().and_then(|s| s.to_str());
                if matches!(ext, Some("yaml") | Some("yml") | Some("json")) {
                    if let Ok(config) = PathConfig::from_file(&path) {
                        self.add(config);
                        count += 1;
                    }
                }
            }
        }

        Ok(count)
    }

    /// Add a path configuration to the library
    pub fn add(&mut self, config: PathConfig) {
        let map = config.map.clone().unwrap_or_else(|| "default".to_string());
        let mode = config.mode.clone().unwrap_or_else(|| "default".to_string());
        let team_label = config
            .team
            .map(|t| {
                let base = t.label().to_string();
                if config.requires_bomb {
                    format!("{}.bomb", base)
                } else {
                    base
                }
            })
            .unwrap_or_else(|| "any".to_string());

        self.paths
            .entry(map)
            .or_default()
            .entry(mode)
            .or_default()
            .entry(team_label)
            .or_default()
            .push(config);
    }

    /// Get path configurations for the given parameters
    pub fn get(&self, map: &str, mode: &str, team: Team, bomb: bool) -> Option<&Vec<PathConfig>> {
        let team_label = if bomb {
            format!("{}.bomb", team.label())
        } else {
            team.label().to_string()
        };

        self.paths
            .get(map)?
            .get(mode)?
            .get(&team_label)
            .or_else(|| {
                // Fallback to non-bomb version
                self.paths.get(map)?.get(mode)?.get(team.label())
            })
    }

    /// Get a random path configuration for the given parameters
    pub fn get_random(
        &self,
        map: &str,
        mode: &str,
        team: Team,
        bomb: bool,
    ) -> Option<&PathConfig> {
        use rand::seq::SliceRandom;
        let configs = self.get(map, mode, team, bomb)?;
        configs.choose(&mut rand::thread_rng())
    }

    /// Create a PathVM for the given parameters
    pub fn create_vm(
        &self,
        map: &str,
        mode: &str,
        team: Team,
        bomb: bool,
        last: bool,
        fast: bool,
        no_buy: bool,
    ) -> Result<PathVM, PathError> {
        let config = self.get_random(map, mode, team, bomb).ok_or_else(|| {
            PathError::PathNotFound {
                map: map.to_string(),
                mode: mode.to_string(),
                team: team.label().to_string(),
            }
        })?;

        config.create_vm(team, bomb, last, fast, no_buy)
    }

    /// List all available map names
    pub fn maps(&self) -> Vec<&str> {
        self.paths.keys().map(|s| s.as_str()).collect()
    }

    /// List all modes for a map
    pub fn modes(&self, map: &str) -> Vec<&str> {
        self.paths
            .get(map)
            .map(|m| m.keys().map(|s| s.as_str()).collect())
            .unwrap_or_default()
    }
}

/// Validate a path configuration
pub fn validate_config(config: &PathConfig) -> Result<(), PathError> {
    // Check that path has at least one node
    if config.path.is_empty() {
        return Err(PathError::InvalidConfig(
            "Path must have at least one node".to_string(),
        ));
    }

    // Try to build with a dummy context to check for errors
    let mut ctx = BuilderContext::new(Team::T, false, false, false, false);
    config.build(&mut ctx)?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_yaml_parsing() {
        let yaml = r#"
name: "test_path"
map: "de_inferno"
mode: "scrimcomp2v2"
team: t
path:
  - move:
      keys: [W, A]
    duration: 3.0
  - key:
      key: F
    duration: 0.5
"#;

        let config = PathConfig::from_yaml(yaml).unwrap();
        assert_eq!(config.name, "test_path");
        assert_eq!(config.map, Some("de_inferno".to_string()));
        assert_eq!(config.team, Some(Team::T));
        assert_eq!(config.path.len(), 2);
    }

    #[test]
    fn test_create_vm() {
        let yaml = r#"
name: "test"
path:
  - move:
      keys: [W]
    duration: 1.0
"#;

        let config = PathConfig::from_yaml(yaml).unwrap();
        let vm = config.create_vm(Team::T, false, false, false, false).unwrap();
        assert_eq!(vm.remaining_edges(), 1);
    }
}
