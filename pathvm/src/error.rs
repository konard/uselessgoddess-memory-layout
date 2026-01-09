//! Error types for PathVM

use thiserror::Error;

#[derive(Error, Debug)]
pub enum PathError {
    #[error("Failed to parse configuration: {0}")]
    ParseError(String),

    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    #[error("Unresolved path reference: {0}")]
    UnresolvedReference(String),

    #[error("Path not found: map={map}, mode={mode}, team={team}")]
    PathNotFound {
        map: String,
        mode: String,
        team: String,
    },

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("YAML parse error: {0}")]
    YamlError(#[from] serde_yaml::Error),

    #[error("JSON parse error: {0}")]
    JsonError(#[from] serde_json::Error),

    #[error("Path execution error: {0}")]
    ExecutionError(String),
}

impl From<PathError> for pyo3::PyErr {
    fn from(err: PathError) -> pyo3::PyErr {
        pyo3::exceptions::PyRuntimeError::new_err(err.to_string())
    }
}
