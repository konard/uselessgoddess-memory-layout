//! Python bindings via PyO3
//!
//! This module exposes PathVM functionality to Python for integration
//! with the existing codebase.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::sync::Mutex;

use crate::action::{ActionRequest, MouseButton, Team};
use crate::config::PathConfig;
use crate::path::PathVM;

/// Python-exposed Team enum
#[pyclass(eq, eq_int)]
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum PyTeam {
    T = 0,
    CT = 1,
}

impl From<Team> for PyTeam {
    fn from(team: Team) -> Self {
        match team {
            Team::T => PyTeam::T,
            Team::CT => PyTeam::CT,
        }
    }
}

impl From<PyTeam> for Team {
    fn from(team: PyTeam) -> Self {
        match team {
            PyTeam::T => Team::T,
            PyTeam::CT => Team::CT,
        }
    }
}

#[pymethods]
impl PyTeam {
    #[staticmethod]
    fn from_str(s: &str) -> PyResult<Self> {
        match s.to_lowercase().as_str() {
            "t" | "terrorist" => Ok(PyTeam::T),
            "ct" | "counter-terrorist" => Ok(PyTeam::CT),
            _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Invalid team: {}",
                s
            ))),
        }
    }

    fn enemy(&self) -> PyTeam {
        match self {
            PyTeam::T => PyTeam::CT,
            PyTeam::CT => PyTeam::T,
        }
    }

    fn label(&self) -> &'static str {
        match self {
            PyTeam::T => "t",
            PyTeam::CT => "ct",
        }
    }
}

/// Python-exposed action request
#[pyclass]
#[derive(Clone)]
pub struct PyActionRequest {
    inner: ActionRequest,
}

#[pymethods]
impl PyActionRequest {
    /// Get the action type as a string
    #[getter]
    fn action_type(&self) -> &'static str {
        match &self.inner {
            ActionRequest::KeyPress { .. } => "key_press",
            ActionRequest::KeyRelease { .. } => "key_release",
            ActionRequest::MousePress { .. } => "mouse_press",
            ActionRequest::MouseRelease { .. } => "mouse_release",
            ActionRequest::MouseMove { .. } => "mouse_move",
            ActionRequest::Rotate { .. } => "rotate",
            ActionRequest::ChangeTeam { .. } => "change_team",
            ActionRequest::Buy { .. } => "buy",
            ActionRequest::WeaponSlot { .. } => "weapon_slot",
            ActionRequest::None => "none",
        }
    }

    /// Get keys for key_press/key_release actions
    fn get_keys(&self) -> Vec<u32> {
        match &self.inner {
            ActionRequest::KeyPress { keys, .. } | ActionRequest::KeyRelease { keys } => {
                keys.iter().map(|k| k.to_vk_code()).collect()
            }
            _ => vec![],
        }
    }

    /// Check if keys should be held
    fn is_hold(&self) -> bool {
        match &self.inner {
            ActionRequest::KeyPress { hold, .. } => *hold,
            _ => false,
        }
    }

    /// Get mouse button for mouse actions
    fn get_mouse_button(&self) -> Option<&'static str> {
        match &self.inner {
            ActionRequest::MousePress { button } | ActionRequest::MouseRelease { button } => {
                Some(match button {
                    MouseButton::Left => "left",
                    MouseButton::Right => "right",
                    MouseButton::Middle => "middle",
                })
            }
            _ => None,
        }
    }

    /// Get mouse press flag
    fn get_mouse_press_flag(&self) -> Option<u32> {
        match &self.inner {
            ActionRequest::MousePress { button } => Some(button.press_flag()),
            _ => None,
        }
    }

    /// Get mouse release flag
    fn get_mouse_release_flag(&self) -> Option<u32> {
        match &self.inner {
            ActionRequest::MouseRelease { button } => Some(button.release_flag()),
            _ => None,
        }
    }

    /// Get mouse move delta
    fn get_mouse_delta(&self) -> Option<(f64, f64)> {
        match &self.inner {
            ActionRequest::MouseMove { dx, dy } => Some((*dx, *dy)),
            _ => None,
        }
    }

    /// Get rotation parameters
    fn get_rotation(&self) -> Option<(f64, f64, f64)> {
        match &self.inner {
            ActionRequest::Rotate {
                target,
                precision,
                max_angle,
            } => Some((*target, *precision, *max_angle)),
            _ => None,
        }
    }

    /// Get team change
    fn get_team_change(&self) -> Option<PyTeam> {
        match &self.inner {
            ActionRequest::ChangeTeam { team } => team.map(PyTeam::from),
            _ => None,
        }
    }

    /// Get weapon slot
    fn get_weapon_slot(&self) -> Option<u8> {
        match &self.inner {
            ActionRequest::WeaponSlot { slot } => Some(*slot),
            _ => None,
        }
    }

    /// Get buy items as list of (category, item) tuples
    fn get_buy_items(&self, py: Python<'_>) -> PyObject {
        match &self.inner {
            ActionRequest::Buy { items } => {
                let list = PyList::empty(py);
                for item in items {
                    let tuple = (item.category, item.item);
                    list.append(tuple).unwrap();
                }
                list.into()
            }
            _ => PyList::empty(py).into(),
        }
    }

    /// Convert to dict for easier Python access
    fn to_dict(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("type", self.action_type())?;

        match &self.inner {
            ActionRequest::KeyPress { keys, hold } => {
                dict.set_item("keys", keys.iter().map(|k| k.to_vk_code()).collect::<Vec<_>>())?;
                dict.set_item("hold", *hold)?;
            }
            ActionRequest::KeyRelease { keys } => {
                dict.set_item("keys", keys.iter().map(|k| k.to_vk_code()).collect::<Vec<_>>())?;
            }
            ActionRequest::MousePress { button } => {
                dict.set_item("button", format!("{:?}", button).to_lowercase())?;
                dict.set_item("flag", button.press_flag())?;
            }
            ActionRequest::MouseRelease { button } => {
                dict.set_item("button", format!("{:?}", button).to_lowercase())?;
                dict.set_item("flag", button.release_flag())?;
            }
            ActionRequest::MouseMove { dx, dy } => {
                dict.set_item("dx", *dx)?;
                dict.set_item("dy", *dy)?;
            }
            ActionRequest::Rotate {
                target,
                precision,
                max_angle,
            } => {
                dict.set_item("target", *target)?;
                dict.set_item("precision", *precision)?;
                dict.set_item("max_angle", *max_angle)?;
            }
            ActionRequest::ChangeTeam { team } => {
                dict.set_item("team", team.map(|t| t.label()))?;
            }
            ActionRequest::Buy { items } => {
                let list = PyList::empty(py);
                for item in items {
                    let d = PyDict::new(py);
                    d.set_item("category", item.category)?;
                    d.set_item("item", item.item)?;
                    list.append(d)?;
                }
                dict.set_item("items", list)?;
            }
            ActionRequest::WeaponSlot { slot } => {
                dict.set_item("slot", *slot)?;
            }
            ActionRequest::None => {}
        }

        Ok(dict.into())
    }
}

/// Python-exposed path configuration
#[pyclass]
#[derive(Clone)]
pub struct PyPathConfig {
    inner: PathConfig,
}

#[pymethods]
impl PyPathConfig {
    #[new]
    fn new(yaml_or_json: &str) -> PyResult<Self> {
        let inner = PathConfig::from_yaml(yaml_or_json)
            .or_else(|_| PathConfig::from_json(yaml_or_json))
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(Self { inner })
    }

    #[staticmethod]
    fn from_file(path: &str) -> PyResult<Self> {
        let inner = PathConfig::from_file(path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
        Ok(Self { inner })
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn map(&self) -> Option<&str> {
        self.inner.map.as_deref()
    }

    #[getter]
    fn mode(&self) -> Option<&str> {
        self.inner.mode.as_deref()
    }

    #[getter]
    fn team(&self) -> Option<PyTeam> {
        self.inner.team.map(PyTeam::from)
    }

    #[getter]
    fn requires_bomb(&self) -> bool {
        self.inner.requires_bomb
    }

    #[getter]
    fn description(&self) -> Option<&str> {
        self.inner.description.as_deref()
    }

    fn validate(&self) -> PyResult<()> {
        crate::config::validate_config(&self.inner)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }
}

/// Python-exposed PathVM
#[pyclass]
pub struct PyPathVM {
    inner: Mutex<PathVM>,
}

#[pymethods]
impl PyPathVM {
    /// Create a new PathVM from a configuration
    #[new]
    fn new(config: &PyPathConfig, team: PyTeam, bomb: bool, last: bool, fast: bool, no_buy: bool) -> PyResult<Self> {
        let vm = config
            .inner
            .create_vm(team.into(), bomb, last, fast, no_buy)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(Self {
            inner: Mutex::new(vm),
        })
    }

    /// Create from YAML string
    #[staticmethod]
    fn from_yaml(yaml: &str, team: PyTeam, bomb: bool, last: bool, fast: bool, no_buy: bool) -> PyResult<Self> {
        let config = PyPathConfig::new(yaml)?;
        Self::new(&config, team, bomb, last, fast, no_buy)
    }

    /// Create from file
    #[staticmethod]
    fn from_file(path: &str, team: PyTeam, bomb: bool, last: bool, fast: bool, no_buy: bool) -> PyResult<Self> {
        let config = PyPathConfig::from_file(path)?;
        Self::new(&config, team, bomb, last, fast, no_buy)
    }

    /// Step the path forward
    ///
    /// Returns (completed, requests, team_change)
    fn step(&self, delta: f64, py: Python<'_>) -> PyResult<PyObject> {
        let mut vm = self.inner.lock().unwrap();
        let result = vm.step(delta);

        let requests = PyList::empty(py);
        for req in result.requests {
            requests.append(PyActionRequest { inner: req }.to_dict(py)?)?;
        }

        let dict = PyDict::new(py);
        dict.set_item("completed", result.completed)?;
        dict.set_item("requests", requests)?;
        dict.set_item(
            "team_change",
            result.team_change.map(|t| t.label().to_string()),
        )?;

        Ok(dict.into())
    }

    /// Get current team
    fn team(&self) -> PyTeam {
        let vm = self.inner.lock().unwrap();
        PyTeam::from(vm.team())
    }

    /// Check if completed
    fn is_completed(&self) -> bool {
        let vm = self.inner.lock().unwrap();
        vm.is_completed()
    }

    /// Get remaining edge count
    fn remaining_edges(&self) -> usize {
        let vm = self.inner.lock().unwrap();
        vm.remaining_edges()
    }

    /// Get direction as int (-1 left, 1 right)
    fn direction(&self) -> i8 {
        let vm = self.inner.lock().unwrap();
        vm.direction().value()
    }
}

/// Load a path configuration from YAML
#[pyfunction]
pub fn load_path_from_yaml(yaml: &str) -> PyResult<PyPathConfig> {
    PyPathConfig::new(yaml)
}

/// Load a path configuration from JSON
#[pyfunction]
pub fn load_path_from_json(json: &str) -> PyResult<PyPathConfig> {
    let inner = PathConfig::from_json(json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(PyPathConfig { inner })
}

/// Validate a path configuration
#[pyfunction]
pub fn validate_config(config: &PyPathConfig) -> PyResult<()> {
    config.validate()
}
