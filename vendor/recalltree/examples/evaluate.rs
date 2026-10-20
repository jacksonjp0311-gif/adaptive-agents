use recalltree::*;
fn main() {
    let mut s = State::default();
    for n in 0..24 {
        let r = Record {
            id: format!("r{n:02}"),
            role: if n % 2 == 0 { "coder" } else { "reviewer" }.into(),
            scope: "fixture".into(),
            text: format!("Synthetic build check {n}"),
            kind: Kind::Observation,
            evidence: vec![Evidence {
                uri: format!("fixture://{n}"),
                available: false,
            }],
            version: 1,
            status: "active".into(),
            applicability: "Synthetic only".into(),
            shared: n % 3 == 0,
            supersedes: vec![],
            conflicts: vec![],
            expires_at: None,
        };
        s.records.insert(r.id.clone(), r);
    }
    println!("budget_bytes,selected,serialized_bytes,equal_to_unified");
    for budget in [512, 1024, 2048, 4096, 8192] {
        let a = retrieve(&s, "coder", "fixture", "build", 0, budget).unwrap();
        let b = unified_baseline(&s, "coder", "fixture", "build", 0, budget).unwrap();
        let bytes = serde_json::to_vec(&a).unwrap();
        assert_eq!(bytes, serde_json::to_vec(&b).unwrap());
        println!("{budget},{},{},true", a.records.len(), bytes.len());
    }
}
