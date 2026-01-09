//! Path execution engine
//!
//! The PathVM is responsible for stepping through a sequence of edges
//! and generating action requests for Python to execute.

use crate::action::{ActionRequest, EdgeDef, RuntimeAction, Team};
use crate::builder::{BuilderContext, Direction};

/// Step result from path execution
#[derive(Debug, Clone)]
pub struct StepResult {
    /// Whether the path has completed
    pub completed: bool,
    /// Action requests to execute
    pub requests: Vec<ActionRequest>,
    /// Team change request (if any)
    pub team_change: Option<Team>,
}

impl StepResult {
    pub fn new() -> Self {
        Self {
            completed: false,
            requests: Vec::new(),
            team_change: None,
        }
    }
}

impl Default for StepResult {
    fn default() -> Self {
        Self::new()
    }
}

/// Path execution engine
#[derive(Debug)]
pub struct PathVM {
    /// Remaining edges to execute
    edges: Vec<EdgeDef>,
    /// Currently executing action
    current: Option<RuntimeAction>,
    /// Current team
    team: Team,
    /// Current direction
    direction: Direction,
    /// Whether the path has completed
    completed: bool,
}

impl PathVM {
    /// Create a new PathVM with the given edges and initial team
    pub fn new(edges: Vec<EdgeDef>, team: Team) -> Self {
        let completed = edges.is_empty();
        Self {
            edges,
            current: None,
            team,
            direction: Direction::Left,
            completed,
        }
    }

    /// Get the current team
    pub fn team(&self) -> Team {
        self.team
    }

    /// Get the current direction
    pub fn direction(&self) -> Direction {
        self.direction
    }

    /// Check if the path is completed
    pub fn is_completed(&self) -> bool {
        self.completed
    }

    /// Get remaining edge count
    pub fn remaining_edges(&self) -> usize {
        self.edges.len() + if self.current.is_some() { 1 } else { 0 }
    }

    /// Step the path forward by delta time
    ///
    /// Returns action requests that should be executed by Python
    pub fn step(&mut self, delta: f64) -> StepResult {
        let mut result = StepResult::new();

        if self.completed {
            result.completed = true;
            return result;
        }

        // Get or start current action
        if self.current.is_none() {
            if self.edges.is_empty() {
                self.completed = true;
                result.completed = true;
                return result;
            }
            let edge = self.edges.remove(0);
            self.current = Some(RuntimeAction::new(edge));
        }

        // Step current action
        if let Some(ref mut action) = self.current {
            let (completed, requests) = action.step(delta, self.team);
            result.requests = requests;

            // Check for team change in requests
            for req in &result.requests {
                if let ActionRequest::ChangeTeam { team } = req {
                    let new_team = team.unwrap_or_else(|| self.team.enemy());
                    result.team_change = Some(new_team);
                    self.team = new_team;
                }
            }

            if completed {
                self.current = None;
            }
        }

        result
    }

    /// Append more edges to the path
    pub fn append(&mut self, edges: Vec<EdgeDef>) {
        self.edges.extend(edges);
        self.completed = false;
    }

    /// Set the direction
    pub fn set_direction(&mut self, direction: Direction) {
        self.direction = direction;
    }

    /// Create a BuilderContext for this path
    pub fn builder_context(&self, bomb: bool, last: bool, fast: bool, no_buy: bool) -> BuilderContext {
        BuilderContext::new(self.team, bomb, last, fast, no_buy)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::action::{ActionDef, Key};

    #[test]
    fn test_empty_path() {
        let mut vm = PathVM::new(vec![], Team::T);
        let result = vm.step(0.1);
        assert!(result.completed);
    }

    #[test]
    fn test_single_action() {
        let edges = vec![EdgeDef::new(
            ActionDef::Key {
                key: Key::W,
                hold: false,
            },
            0.5,
        )];
        let mut vm = PathVM::new(edges, Team::T);

        // First step - action starts
        let result = vm.step(0.1);
        assert!(!result.completed);
        assert_eq!(result.requests.len(), 1);

        // More steps until completion
        for _ in 0..4 {
            let result = vm.step(0.1);
            assert!(!result.completed);
        }

        // Final step - action completes
        let result = vm.step(0.1);
        assert!(result.completed);
    }

    #[test]
    fn test_team_change() {
        let edges = vec![EdgeDef::new(ActionDef::ChangeTeam { team: None }, 0.1)];
        let mut vm = PathVM::new(edges, Team::T);

        let result = vm.step(0.1);
        assert_eq!(result.team_change, Some(Team::CT));
        assert_eq!(vm.team(), Team::CT);
    }
}
