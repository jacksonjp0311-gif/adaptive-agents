use recalltree::*;
use std::sync::atomic::{AtomicUsize, Ordering};
static N: AtomicUsize = AtomicUsize::new(0);
fn engine(l: Limits) -> Engine {
    let p = std::env::temp_dir().join(format!(
        "recalltree-test-{}-{}",
        std::process::id(),
        N.fetch_add(1, Ordering::SeqCst)
    ));
    Engine::open(p, l).unwrap()
}
fn record(id: &str) -> Record {
    Record {
        id: id.into(),
        role: "coder".into(),
        scope: "project".into(),
        text: "Unicode 🦀 quoted \"build\" observation".into(),
        kind: Kind::Observation,
        evidence: vec![Evidence {
            uri: "fixture://log".into(),
            available: false,
        }],
        version: 1,
        status: "active".into(),
        applicability: "fixture".into(),
        shared: false,
        supersedes: vec![],
        conflicts: vec![],
        expires_at: None,
    }
}
#[test]
fn precommit_preserves_work() {
    let e = engine(Limits::default());
    e.ingest("r", record("a"), b"scratch").unwrap();
    assert!(e.finalize("r", Fault::BeforeCommit).is_err());
    assert_eq!(e.working_bytes(), 7);
    assert!(e.state().runs.is_empty());
    e.finalize("r", Fault::None).unwrap();
    assert_eq!(e.working_bytes(), 0);
}
#[test]
fn postcommit_replay_is_idempotent() {
    let e = engine(Limits::default());
    e.ingest("r", record("a"), b"scratch").unwrap();
    assert!(e.finalize("r", Fault::AfterCommit).is_err());
    e.finalize("r", Fault::None).unwrap();
    e.finalize("r", Fault::None).unwrap();
    assert_eq!(e.state().records.len(), 1);
    assert_eq!(e.state().edges.len(), 1);
}
#[test]
fn cleanup_failure_keeps_durable_state() {
    let e = engine(Limits::default());
    e.ingest("r", record("a"), b"scratch").unwrap();
    assert!(e.finalize("r", Fault::Cleanup).is_err());
    assert_eq!(e.state().runs.len(), 1);
    assert_eq!(e.working_bytes(), 7);
    e.finalize("r", Fault::None).unwrap();
}
#[test]
fn byte_budget_and_equivalence() {
    let e = engine(Limits::default());
    for id in ["a", "b", "c"] {
        e.ingest("r", record(id), b"").unwrap();
    }
    e.finalize("r", Fault::None).unwrap();
    for budget in [256, 512, 1024, 2048] {
        let a = retrieve(&e.state(), "coder", "project", "build", 0, budget);
        let b = unified_baseline(&e.state(), "coder", "project", "build", 0, budget);
        match (a, b) {
            (Ok(a), Ok(b)) => {
                let bytes = serde_json::to_vec(&a).unwrap();
                assert!(bytes.len() <= budget);
                assert_eq!(bytes, serde_json::to_vec(&b).unwrap());
            }
            (Err(a), Err(b)) => assert_eq!(a, b),
            _ => panic!("mismatch"),
        }
    }
}
#[test]
fn envelope_failure_is_explicit() {
    assert!(retrieve(&State::default(), "r", "s", "", 0, 1)
        .unwrap_err()
        .contains("envelope"));
}
#[test]
fn provenance_and_kind_survive() {
    let e = engine(Limits::default());
    e.ingest("r", record("a"), b"heavy").unwrap();
    e.finalize("r", Fault::None).unwrap();
    let p = retrieve(&e.state(), "coder", "project", "", 0, 2048).unwrap();
    assert_eq!(p.records[0], record("a"));
}
#[test]
fn scoped_expiry_and_supersession() {
    let mut s = State::default();
    let a = record("a");
    let mut b = record("b");
    b.supersedes.push("a".into());
    s.records.insert(a.id.clone(), a);
    s.records.insert(b.id.clone(), b);
    assert_eq!(
        retrieve(&s, "coder", "project", "", 0, 2048)
            .unwrap()
            .records
            .len(),
        1
    );
    assert!(retrieve(&s, "other", "project", "", 0, 2048)
        .unwrap()
        .records
        .is_empty());
    s.records.get_mut("b").unwrap().expires_at = Some(1);
    assert!(retrieve(&s, "coder", "project", "", 2, 2048)
        .unwrap()
        .records
        .is_empty());
}
#[test]
fn candidate_cannot_be_shared() {
    let e = engine(Limits::default());
    let mut r = record("a");
    r.kind = Kind::CandidateLesson;
    r.shared = true;
    assert!(e.ingest("r", r, b"").is_err());
}
#[test]
fn bounded_store_does_not_delete() {
    let e = engine(Limits {
        records: 2,
        ..Limits::default()
    });
    e.ingest("r", record("a"), b"scratch").unwrap();
    assert!(e.finalize("r", Fault::None).is_err());
    assert_eq!(e.working_bytes(), 7);
}
#[test]
fn generation_retention_stops_writes() {
    let e = engine(Limits {
        generations: 1,
        ..Limits::default()
    });
    e.ingest("r", record("a"), b"").unwrap();
    e.finalize("r", Fault::None).unwrap();
    e.ingest("s", record("b"), b"").unwrap();
    assert!(e.finalize("s", Fault::None).is_err());
    assert_eq!(e.state().records.len(), 1);
}
#[test]
fn concurrent_finalize_is_serialized() {
    let e = engine(Limits::default());
    e.ingest("r", record("a"), b"scratch").unwrap();
    std::thread::scope(|s| {
        for _ in 0..8 {
            s.spawn(|| e.finalize("r", Fault::None).unwrap());
        }
    });
    assert_eq!(e.state().records.len(), 1);
    assert!(e.ingest("r", record("b"), b"").is_err());
}
#[test]
fn working_limit_and_duplicate_ids() {
    let e = engine(Limits::default());
    e.ingest("r", record("a"), b"").unwrap();
    assert!(e.ingest("s", record("a"), b"").is_err());
    assert!(e.ingest("s", record("b"), &vec![0; 100001]).is_err());
}
#[test]
fn restart_after_commit_recovers_marker() {
    let p = std::env::temp_dir().join(format!("recalltree-restart-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&p);
    {
        let e = Engine::open(&p, Limits::default()).unwrap();
        e.ingest("r", record("a"), b"scratch").unwrap();
        assert!(e.finalize("r", Fault::AfterCommit).is_err());
    }
    let e = Engine::open(&p, Limits::default()).unwrap();
    e.finalize("r", Fault::None).unwrap();
    assert_eq!(e.state().records.len(), 1);
    assert_eq!(e.working_bytes(), 0);
    assert!(Engine::open(&p, Limits::default()).is_err());
}

#[test]
fn invisible_scope_cannot_supersede_or_remove_omissions() {
    let mut state = State::default();
    let a = record("a");
    let mut b = record("b");
    b.scope = "private-other-project".into();
    b.supersedes.push("a".into());
    state.records.insert(a.id.clone(), a);
    state.records.insert(b.id.clone(), b);
    let full = retrieve(&state, "coder", "project", "", 0, 2048).unwrap();
    assert_eq!(
        full.records
            .iter()
            .map(|r| r.id.as_str())
            .collect::<Vec<_>>(),
        ["a"]
    );
    let bounded = retrieve(&state, "coder", "project", "", 0, 256).unwrap();
    assert!(bounded.records.is_empty());
    assert_eq!(bounded.omitted, ["a"]);
}

#[test]
fn supersession_requires_visible_role_and_active_status() {
    let mut state = State::default();
    state.records.insert("a".into(), record("a"));
    let mut b = record("b");
    b.role = "reviewer".into();
    b.supersedes.push("a".into());
    state.records.insert("b".into(), b);
    assert_eq!(
        retrieve(&state, "coder", "project", "", 0, 2048)
            .unwrap()
            .records[0]
            .id,
        "a"
    );
    state.records.get_mut("b").unwrap().shared = true;
    assert_eq!(
        retrieve(&state, "coder", "project", "", 0, 2048)
            .unwrap()
            .records[0]
            .id,
        "b"
    );
    state.records.get_mut("b").unwrap().status = "archived".into();
    assert_eq!(
        retrieve(&state, "coder", "project", "", 0, 2048)
            .unwrap()
            .records[0]
            .id,
        "a"
    );
    state.records.get_mut("b").unwrap().shared = false;
    state.records.get_mut("b").unwrap().role = "coder".into();
    state.records.get_mut("b").unwrap().status = "active".into();
    assert_eq!(
        retrieve(&state, "coder", "project", "", 0, 2048)
            .unwrap()
            .records[0]
            .id,
        "b"
    );
}
