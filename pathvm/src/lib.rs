//! PathVM - A portable path execution engine
//!
//! This crate provides a behavior tree-like execution engine for game paths,
//! designed to be configured via YAML files for non-programmers while
//! supporting advanced features like random branching and conditional logic.
//!
//! # Architecture
//!
//! The system is built around these core concepts:
//!
//! - **Actions**: Atomic operations (move, key press, rotate, etc.)
//! - **Edges**: Actions with optional duration
//! - **Builders**: Composable nodes that generate edges (Select, Maybe, If)
//! - **Paths**: Executable sequences of edges
//! - **PathVM**: The execution engine that steps through paths
//!
//! # Configuration
//!
//! Paths can be defined in YAML format:
//!
//! ```yaml
//! name: "de_inferno_t_mid"
//! team: "T"
//! mode: "scrimcomp2v2"
//!
//! path:
//!   - rotate: { target: 0, precision: 5.0 }
//!     duration: 40.0
//!   - move: [W, A]
//!     duration: 3.0
//!   - maybe:
//!       chance: 0.25
//!       then:
//!         - change_team: "T"
//! ```

mod action;
mod builder;
mod config;
mod error;
mod path;
mod python;

pub use action::*;
pub use builder::*;
pub use config::*;
pub use error::*;
pub use path::*;

use pyo3::prelude::*;

/// Initialize the PathVM Python module
#[pymodule]
fn pathvm(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize logging
    let _ = env_logger::try_init();

    // Register Python classes
    m.add_class::<python::PyPathVM>()?;
    m.add_class::<python::PyPathConfig>()?;
    m.add_class::<python::PyActionRequest>()?;
    m.add_class::<python::PyTeam>()?;

    // Register helper functions
    m.add_function(wrap_pyfunction!(python::load_path_from_yaml, m)?)?;
    m.add_function(wrap_pyfunction!(python::load_path_from_json, m)?)?;
    m.add_function(wrap_pyfunction!(python::validate_config, m)?)?;

    Ok(())
}
