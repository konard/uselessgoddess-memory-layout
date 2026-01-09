//! Core action types for the path execution engine
//!
//! Actions represent atomic operations that can be performed during path execution.
//! Each action can be executed and released (for held keys/buttons).

use serde::{Deserialize, Serialize};

/// Team identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Team {
    T,
    CT,
}

impl Team {
    /// Get the enemy team
    pub fn enemy(&self) -> Self {
        match self {
            Team::T => Team::CT,
            Team::CT => Team::T,
        }
    }

    /// Get the team label
    pub fn label(&self) -> &'static str {
        match self {
            Team::T => "t",
            Team::CT => "ct",
        }
    }
}

/// Key identifiers matching Windows virtual key codes
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Key {
    // Movement keys
    W,
    A,
    S,
    D,
    // Modifier keys
    Shift,
    Ctrl,
    // Action keys
    E,
    F,
    B,
    K,
    L,
    // Number keys
    #[serde(rename = "0")]
    Num0,
    #[serde(rename = "1")]
    Num1,
    #[serde(rename = "2")]
    Num2,
    #[serde(rename = "3")]
    Num3,
    #[serde(rename = "4")]
    Num4,
    #[serde(rename = "5")]
    Num5,
    #[serde(rename = "6")]
    Num6,
    #[serde(rename = "7")]
    Num7,
    #[serde(rename = "8")]
    Num8,
    #[serde(rename = "9")]
    Num9,
    // Function keys
    F3,
    Esc,
}

impl Key {
    /// Convert to Windows virtual key code
    pub fn to_vk_code(&self) -> u32 {
        match self {
            Key::W => 0x57,
            Key::A => 0x41,
            Key::S => 0x53,
            Key::D => 0x44,
            Key::Shift => 0x10,
            Key::Ctrl => 0x11,
            Key::E => 0x45,
            Key::F => 0x46,
            Key::B => 0x42,
            Key::K => 0x4B,
            Key::L => 0x4C,
            Key::Num0 => 0x30,
            Key::Num1 => 0x31,
            Key::Num2 => 0x32,
            Key::Num3 => 0x33,
            Key::Num4 => 0x34,
            Key::Num5 => 0x35,
            Key::Num6 => 0x36,
            Key::Num7 => 0x37,
            Key::Num8 => 0x38,
            Key::Num9 => 0x39,
            Key::F3 => 0x72,
            Key::Esc => 0x1B,
        }
    }
}

/// Mouse button identifiers
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MouseButton {
    Left,
    Right,
    Middle,
}

impl MouseButton {
    /// Get the mouse event flag for pressing
    pub fn press_flag(&self) -> u32 {
        match self {
            MouseButton::Left => 0x0002,   // MOUSEEVENTF_LEFTDOWN
            MouseButton::Right => 0x0008,  // MOUSEEVENTF_RIGHTDOWN
            MouseButton::Middle => 0x0020, // MOUSEEVENTF_MIDDLEDOWN
        }
    }

    /// Get the mouse event flag for releasing
    pub fn release_flag(&self) -> u32 {
        self.press_flag() << 1
    }
}

/// Action request that gets sent to Python for execution
///
/// This is the output of the PathVM - it tells Python what inputs to simulate.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ActionRequest {
    /// Press one or more keys
    KeyPress {
        keys: Vec<Key>,
        hold: bool,
    },
    /// Release one or more keys
    KeyRelease {
        keys: Vec<Key>,
    },
    /// Press a mouse button
    MousePress {
        button: MouseButton,
    },
    /// Release a mouse button
    MouseRelease {
        button: MouseButton,
    },
    /// Move the mouse relatively
    MouseMove {
        dx: f64,
        dy: f64,
    },
    /// Rotate to a target angle (requires frame analysis)
    Rotate {
        target: f64,
        precision: f64,
        max_angle: f64,
    },
    /// Change active team
    ChangeTeam {
        team: Option<Team>,
    },
    /// Buy items from the buy menu
    Buy {
        items: Vec<BuyItem>,
    },
    /// Switch to a weapon slot
    WeaponSlot {
        slot: u8,
    },
    /// Do nothing (wait)
    None,
}

/// Buy menu item
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuyItem {
    pub category: u8,
    pub item: u8,
}

/// Core action definition from configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ActionDef {
    /// Move with keys (e.g., [W, A] for forward-left)
    Move {
        keys: Vec<Key>,
        #[serde(default)]
        hold: bool,
    },
    /// Press a single key
    Key {
        key: Key,
        #[serde(default)]
        hold: bool,
    },
    /// Mouse click
    Mouse {
        button: MouseButton,
    },
    /// Relative mouse movement
    MouseMove {
        x: f64,
        y: f64,
    },
    /// Rotate to target angle
    Rotate {
        target: f64,
        #[serde(default = "default_precision")]
        precision: f64,
        #[serde(default = "default_max_angle")]
        max_angle: f64,
    },
    /// Change team
    ChangeTeam {
        team: Option<Team>,
    },
    /// Buy randomly
    BuyRandom {
        #[serde(default)]
        no_buy: bool,
    },
    /// Switch weapon slot
    Weapon {
        slot: u8,
    },
    /// Shoot (uses K key)
    Shoot {
        #[serde(default)]
        hold: bool,
    },
    /// Alt shoot (uses L key)
    AltShoot {
        #[serde(default)]
        hold: bool,
    },
    /// Inspect weapon (F key)
    Inspect {
        #[serde(default)]
        hold: bool,
    },
    /// Wait/do nothing
    Wait,
    /// Aim controller (complex targeting)
    Aim {
        #[serde(default = "default_direction")]
        direction: i8,
        #[serde(default)]
        burst: bool,
    },
}

fn default_precision() -> f64 {
    5.0
}

fn default_max_angle() -> f64 {
    100.0
}

fn default_direction() -> i8 {
    -1
}

/// An edge is an action with a duration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeDef {
    /// The action to perform
    #[serde(flatten)]
    pub action: ActionDef,
    /// Duration in seconds (default: 0.25)
    #[serde(default = "default_duration")]
    pub duration: f64,
}

fn default_duration() -> f64 {
    0.25
}

impl EdgeDef {
    pub fn new(action: ActionDef, duration: f64) -> Self {
        Self { action, duration }
    }
}

/// Runtime action state during execution
#[derive(Debug, Clone)]
pub struct RuntimeAction {
    pub edge: EdgeDef,
    pub timer: f64,
    pub released: bool,
}

impl RuntimeAction {
    pub fn new(edge: EdgeDef) -> Self {
        Self {
            edge,
            timer: 0.0,
            released: false,
        }
    }

    /// Step the action forward by delta time
    /// Returns (completed, action_requests)
    pub fn step(&mut self, delta: f64, team: Team) -> (bool, Vec<ActionRequest>) {
        let mut requests = Vec::new();

        if self.timer == 0.0 {
            // First tick - execute the action
            requests.extend(self.execute(delta, team));
        }

        self.timer += delta;

        let completed = self.timer >= self.edge.duration;
        if completed && !self.released {
            requests.extend(self.release());
            self.released = true;
        }

        (completed, requests)
    }

    /// Generate action requests for executing this action
    fn execute(&self, delta: f64, _team: Team) -> Vec<ActionRequest> {
        match &self.edge.action {
            ActionDef::Move { keys, hold } => {
                vec![ActionRequest::KeyPress {
                    keys: keys.clone(),
                    hold: *hold,
                }]
            }
            ActionDef::Key { key, hold } => {
                vec![ActionRequest::KeyPress {
                    keys: vec![*key],
                    hold: *hold,
                }]
            }
            ActionDef::Mouse { button } => {
                vec![ActionRequest::MousePress { button: *button }]
            }
            ActionDef::MouseMove { x, y } => {
                vec![ActionRequest::MouseMove {
                    dx: -x * delta,
                    dy: -y * delta,
                }]
            }
            ActionDef::Rotate {
                target,
                precision,
                max_angle,
            } => {
                vec![ActionRequest::Rotate {
                    target: *target,
                    precision: *precision,
                    max_angle: *max_angle,
                }]
            }
            ActionDef::ChangeTeam { team } => {
                vec![ActionRequest::ChangeTeam { team: *team }]
            }
            ActionDef::BuyRandom { no_buy } => {
                if *no_buy {
                    vec![]
                } else {
                    // Generate random buy sequence
                    self.generate_random_buy()
                }
            }
            ActionDef::Weapon { slot } => {
                vec![ActionRequest::WeaponSlot { slot: *slot }]
            }
            ActionDef::Shoot { hold } => {
                vec![ActionRequest::KeyPress {
                    keys: vec![Key::K],
                    hold: *hold,
                }]
            }
            ActionDef::AltShoot { hold } => {
                vec![ActionRequest::KeyPress {
                    keys: vec![Key::L],
                    hold: *hold,
                }]
            }
            ActionDef::Inspect { hold } => {
                vec![ActionRequest::KeyPress {
                    keys: vec![Key::F],
                    hold: *hold,
                }]
            }
            ActionDef::Wait => {
                vec![ActionRequest::None]
            }
            ActionDef::Aim { direction: _, burst: _ } => {
                // Aim controller is handled specially by Python side
                vec![ActionRequest::None]
            }
        }
    }

    /// Generate release requests when action completes
    fn release(&self) -> Vec<ActionRequest> {
        match &self.edge.action {
            ActionDef::Move { keys, hold } if !*hold => {
                vec![ActionRequest::KeyRelease { keys: keys.clone() }]
            }
            ActionDef::Key { key, hold } if !*hold => {
                vec![ActionRequest::KeyRelease { keys: vec![*key] }]
            }
            ActionDef::Mouse { button } => {
                vec![ActionRequest::MouseRelease { button: *button }]
            }
            ActionDef::Shoot { hold } if !*hold => {
                vec![ActionRequest::KeyRelease { keys: vec![Key::K] }]
            }
            ActionDef::AltShoot { hold } if !*hold => {
                vec![ActionRequest::KeyRelease { keys: vec![Key::L] }]
            }
            ActionDef::Inspect { hold } if !*hold => {
                vec![ActionRequest::KeyRelease { keys: vec![Key::F] }]
            }
            _ => vec![],
        }
    }

    /// Generate random buy sequence
    fn generate_random_buy(&self) -> Vec<ActionRequest> {
        use rand::Rng;
        let mut rng = rand::thread_rng();

        let mut items = Vec::new();

        // 85% chance to buy kevlar/helmet
        if rng.gen::<f64>() < 0.85 {
            items.push(BuyItem {
                category: 1,
                item: 2,
            });
        }

        // Random weapons (0-4 items)
        let amount = rng.gen_range(0..=4);
        let forbidden = [(4, 3), (4, 5), (5, 2)]; // sniper, smoke

        for _ in 0..amount {
            let category = rng.gen_range(2..=5);
            let weapon = rng.gen_range(2..=5);

            if !forbidden.contains(&(category, weapon)) {
                items.push(BuyItem {
                    category,
                    item: weapon,
                });
            }
        }

        vec![ActionRequest::Buy { items }]
    }
}
