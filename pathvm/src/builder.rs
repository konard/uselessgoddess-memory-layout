//! Builder types for composable path construction
//!
//! Builders are used to generate sequences of edges based on context.
//! They support randomization, conditions, and other dynamic behaviors.

use rand::Rng;
use serde::{Deserialize, Serialize};

use crate::action::{ActionDef, EdgeDef, Key, Team};
use crate::error::PathError;

/// Direction constant for path traversal
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Direction {
    Left,
    Right,
}

impl Direction {
    pub fn value(&self) -> i8 {
        match self {
            Direction::Left => -1,
            Direction::Right => 1,
        }
    }
}

impl Default for Direction {
    fn default() -> Self {
        Direction::Left
    }
}

/// Context for building paths
#[derive(Debug, Clone)]
pub struct BuilderContext {
    pub team: Team,
    pub bomb: bool,
    pub last: bool,
    pub burst: bool,
    pub grenade: bool,
    pub recursive: bool,
    pub direction: Direction,
    pub fast: bool,
    pub no_buy: bool,
}

impl BuilderContext {
    pub fn new(team: Team, bomb: bool, last: bool, fast: bool, no_buy: bool) -> Self {
        Self {
            team,
            bomb,
            last,
            burst: false,
            grenade: false,
            recursive: false,
            direction: Direction::Left,
            fast,
            no_buy,
        }
    }
}

/// A node in the path configuration tree
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum PathNode {
    /// A simple edge (action with duration)
    Edge(EdgeDef),
    /// A builder that generates edges
    Builder(BuilderDef),
    /// A reference to another path file
    Reference { path_ref: String },
}

/// Builder definition from configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BuilderDef {
    /// Select one of the options randomly
    Select {
        options: Vec<Vec<PathNode>>,
    },
    /// Execute with a certain probability
    Maybe {
        chance: f64,
        then: Vec<PathNode>,
    },
    /// Conditional execution
    If {
        condition: Condition,
        then: Vec<PathNode>,
        #[serde(rename = "else", default)]
        else_branch: Vec<PathNode>,
    },
    /// Set the direction for subsequent actions
    SetDirection {
        direction: Direction,
    },
    /// Control recursive behavior
    DisableRecursive {
        recursive: bool,
    },
    /// Buy random items
    BuyRandom,
    /// Execute a recursive path with fallback
    Recursive {
        primary: Vec<PathNode>,
        #[serde(default)]
        fallback: Vec<PathNode>,
    },
    /// A list of nodes to execute in sequence
    Sequence {
        nodes: Vec<PathNode>,
    },
}

/// Conditions for If builder
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Condition {
    /// Check if this is the last round
    NotLast,
    IsLast,
    /// Check if player has bomb
    HasBomb,
    NoBomb,
    /// Check team
    IsTeam { team: Team },
    /// Check recursive flag
    NotRecursive,
    IsRecursive,
    /// Check direction
    IsDirection { direction: Direction },
    /// Combined conditions
    And { conditions: Vec<Condition> },
    Or { conditions: Vec<Condition> },
    Not { condition: Box<Condition> },
    /// Always true/false
    Always,
    Never,
}

impl Condition {
    pub fn evaluate(&self, ctx: &BuilderContext) -> bool {
        match self {
            Condition::NotLast => !ctx.last,
            Condition::IsLast => ctx.last,
            Condition::HasBomb => ctx.bomb,
            Condition::NoBomb => !ctx.bomb,
            Condition::IsTeam { team } => ctx.team == *team,
            Condition::NotRecursive => !ctx.recursive,
            Condition::IsRecursive => ctx.recursive,
            Condition::IsDirection { direction } => ctx.direction == *direction,
            Condition::And { conditions } => conditions.iter().all(|c| c.evaluate(ctx)),
            Condition::Or { conditions } => conditions.iter().any(|c| c.evaluate(ctx)),
            Condition::Not { condition } => !condition.evaluate(ctx),
            Condition::Always => true,
            Condition::Never => false,
        }
    }
}

/// Extract edges from a path node
pub fn extract_edges(node: &PathNode, ctx: &mut BuilderContext) -> Result<Vec<EdgeDef>, PathError> {
    match node {
        PathNode::Edge(edge) => Ok(vec![edge.clone()]),
        PathNode::Builder(builder) => extract_builder(builder, ctx),
        PathNode::Reference { path_ref } => {
            // References are resolved at load time
            Err(PathError::UnresolvedReference(path_ref.clone()))
        }
    }
}

/// Extract edges from a list of nodes
pub fn extract_all(nodes: &[PathNode], ctx: &mut BuilderContext) -> Result<Vec<EdgeDef>, PathError> {
    let mut edges = Vec::new();
    for node in nodes {
        edges.extend(extract_edges(node, ctx)?);
    }
    Ok(edges)
}

/// Extract edges from a builder
fn extract_builder(builder: &BuilderDef, ctx: &mut BuilderContext) -> Result<Vec<EdgeDef>, PathError> {
    let mut rng = rand::thread_rng();

    match builder {
        BuilderDef::Select { options } => {
            if options.is_empty() {
                return Ok(vec![]);
            }
            let idx = rng.gen_range(0..options.len());
            extract_all(&options[idx], ctx)
        }

        BuilderDef::Maybe { chance, then } => {
            if rng.gen::<f64>() < *chance {
                extract_all(then, ctx)
            } else {
                Ok(vec![])
            }
        }

        BuilderDef::If {
            condition,
            then,
            else_branch,
        } => {
            if condition.evaluate(ctx) {
                extract_all(then, ctx)
            } else {
                extract_all(else_branch, ctx)
            }
        }

        BuilderDef::SetDirection { direction } => {
            ctx.direction = *direction;
            Ok(vec![])
        }

        BuilderDef::DisableRecursive { recursive } => {
            ctx.recursive = *recursive;
            Ok(vec![])
        }

        BuilderDef::BuyRandom => {
            if ctx.no_buy {
                return Ok(vec![]);
            }

            let mut edges = vec![
                // Open buy menu
                EdgeDef::new(ActionDef::Key { key: Key::B, hold: false }, 0.5),
            ];

            // 85% chance to buy kevlar
            if rng.gen::<f64>() < 0.85 {
                edges.push(EdgeDef::new(
                    ActionDef::Key {
                        key: Key::Num1,
                        hold: false,
                    },
                    0.5,
                ));
                edges.push(EdgeDef::new(
                    ActionDef::Key {
                        key: Key::Num2,
                        hold: false,
                    },
                    0.5,
                ));
            }

            // Random weapons
            let amount = rng.gen_range(0..=4);
            let forbidden = [(4, 3), (4, 5), (5, 2)];

            for _ in 0..amount {
                let category = rng.gen_range(2..=5);
                let weapon = rng.gen_range(2..=5);

                if !forbidden.contains(&(category, weapon)) {
                    let cat_key = match category {
                        2 => Key::Num2,
                        3 => Key::Num3,
                        4 => Key::Num4,
                        5 => Key::Num5,
                        _ => continue,
                    };
                    let weap_key = match weapon {
                        2 => Key::Num2,
                        3 => Key::Num3,
                        4 => Key::Num4,
                        5 => Key::Num5,
                        _ => continue,
                    };

                    if weapon == 5 {
                        ctx.grenade = true;
                    }

                    edges.push(EdgeDef::new(
                        ActionDef::Key {
                            key: cat_key,
                            hold: false,
                        },
                        0.5,
                    ));
                    edges.push(EdgeDef::new(
                        ActionDef::Key {
                            key: weap_key,
                            hold: false,
                        },
                        0.5,
                    ));
                }
            }

            // Close buy menu
            edges.push(EdgeDef::new(
                ActionDef::Key { key: Key::B, hold: false },
                0.5,
            ));

            Ok(edges)
        }

        BuilderDef::Recursive { primary, fallback } => {
            if !ctx.recursive && !ctx.fast {
                ctx.recursive = true;
                extract_all(primary, ctx)
            } else {
                extract_all(fallback, ctx)
            }
        }

        BuilderDef::Sequence { nodes } => extract_all(nodes, ctx),
    }
}
