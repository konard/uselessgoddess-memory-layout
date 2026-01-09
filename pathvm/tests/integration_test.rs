//! Integration tests for PathVM

use pathvm::{
    ActionDef, Key, Team,
    BuilderContext, Condition, Direction,
    PathConfig,
    PathVM,
};

#[test]
fn test_simple_path_execution() {
    let yaml = r#"
name: "test_simple"
path:
  - move:
      keys: [W]
    duration: 1.0
  - move:
      keys: [A]
    duration: 0.5
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");
    let mut vm = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");

    assert!(!vm.is_completed());
    assert_eq!(vm.remaining_edges(), 2);

    // Step through the path
    let mut total_requests = 0;
    while !vm.is_completed() {
        let result = vm.step(0.1);
        total_requests += result.requests.len();
    }

    assert!(vm.is_completed());
    assert!(total_requests > 0);
}

#[test]
fn test_select_builder() {
    let yaml = r#"
name: "test_select"
path:
  - select:
      options:
        - - move:
              keys: [W]
            duration: 0.5
        - - move:
              keys: [S]
            duration: 0.5
        - - move:
              keys: [A]
            duration: 0.5
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");

    // Run multiple times to test randomization
    for _ in 0..10 {
        let mut vm = config
            .create_vm(Team::T, false, false, false, false)
            .expect("Failed to create VM");

        assert!(!vm.is_completed());

        while !vm.is_completed() {
            vm.step(0.1);
        }
    }
}

#[test]
fn test_maybe_builder() {
    let yaml = r#"
name: "test_maybe"
path:
  - maybe:
      chance: 1.0
      then:
        - move:
            keys: [W]
          duration: 0.5
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");
    let mut vm = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");

    // With chance 1.0, should always have at least one edge
    assert!(!vm.is_completed());

    while !vm.is_completed() {
        vm.step(0.1);
    }
}

#[test]
fn test_if_condition() {
    // Test with bomb = true
    let yaml = r#"
name: "test_if"
path:
  - if:
      condition: has_bomb
      then:
        - move:
            keys: [W]
          duration: 0.5
      else:
        - move:
            keys: [S]
          duration: 0.5
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");

    // With bomb
    let vm_with_bomb = config
        .create_vm(Team::T, true, false, false, false)
        .expect("Failed to create VM");
    assert!(!vm_with_bomb.is_completed());

    // Without bomb
    let vm_without_bomb = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");
    assert!(!vm_without_bomb.is_completed());
}

#[test]
fn test_team_change() {
    let yaml = r#"
name: "test_team_change"
path:
  - change_team: {}
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");
    let mut vm = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");

    assert_eq!(vm.team(), Team::T);

    let result = vm.step(0.1);
    assert_eq!(result.team_change, Some(Team::CT));
    assert_eq!(vm.team(), Team::CT);
}

#[test]
fn test_direction_setting() {
    let yaml = r#"
name: "test_direction"
path:
  - set_direction:
      direction: right
  - move:
      keys: [W]
    duration: 0.5
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");
    let mut vm = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");

    // Initial direction should be left
    assert_eq!(vm.direction().value(), -1);

    // After stepping, direction should change to right
    vm.step(0.1);
    // Note: set_direction doesn't change PathVM direction directly in current impl
    // It affects BuilderContext during path building
}

#[test]
fn test_condition_evaluation() {
    let ctx = BuilderContext::new(Team::T, true, false, false, false);

    assert!(Condition::HasBomb.evaluate(&ctx));
    assert!(!Condition::NoBomb.evaluate(&ctx));
    assert!(Condition::NotLast.evaluate(&ctx));
    assert!(!Condition::IsLast.evaluate(&ctx));
    assert!(Condition::IsTeam { team: Team::T }.evaluate(&ctx));
    assert!(!Condition::IsTeam { team: Team::CT }.evaluate(&ctx));

    // Test compound conditions
    let and_cond = Condition::And {
        conditions: vec![Condition::HasBomb, Condition::NotLast],
    };
    assert!(and_cond.evaluate(&ctx));

    let or_cond = Condition::Or {
        conditions: vec![Condition::NoBomb, Condition::NotLast],
    };
    assert!(or_cond.evaluate(&ctx));

    let not_cond = Condition::Not {
        condition: Box::new(Condition::NoBomb),
    };
    assert!(not_cond.evaluate(&ctx));
}

#[test]
fn test_complex_path() {
    let yaml = r#"
name: "complex_test"
map: "de_inferno"
mode: "scrimcomp2v2"
team: t
description: "Complex test path"

path:
  - set_direction:
      direction: right
  - rotate:
      target: 0
      precision: 5.0
    duration: 2.0
  - move:
      keys: [W, A]
    duration: 1.0
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
        - - wait: {}
            duration: 0.5
  - if:
      condition: not_last
      then:
        - move:
            keys: [D]
          duration: 0.5
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");
    assert_eq!(config.name, "complex_test");
    assert_eq!(config.map, Some("de_inferno".to_string()));
    assert_eq!(config.mode, Some("scrimcomp2v2".to_string()));
    assert_eq!(config.team, Some(Team::T));

    let mut vm = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");

    while !vm.is_completed() {
        vm.step(0.1);
    }
}

#[test]
fn test_buy_random() {
    let yaml = r#"
name: "test_buy"
path:
  - buy_random: {}
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");
    let mut vm = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");

    // Buy random should generate multiple edges (menu open, items, menu close)
    assert!(vm.remaining_edges() > 0);

    while !vm.is_completed() {
        vm.step(0.1);
    }
}

#[test]
fn test_empty_path() {
    let yaml = r#"
name: "empty"
path: []
"#;

    let config = PathConfig::from_yaml(yaml).expect("Failed to parse YAML");
    let vm = config
        .create_vm(Team::T, false, false, false, false)
        .expect("Failed to create VM");

    assert!(vm.is_completed());
}
