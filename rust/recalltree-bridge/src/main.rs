//! Local optional bridge. Host supplies authorization; records remain untrusted data.
use recalltree::{retrieve, Engine, Fault, Kind, Limits, Record};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{
    collections::BTreeSet,
    fs,
    io::{self, Read, Write},
    path::PathBuf,
};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    operation: String,
    store: PathBuf,
    store_id: String,
    project_id: String,
    memory_key: String,
    configuration_hash: String,
    #[serde(default)]
    run_id: String,
    #[serde(default)]
    records: Vec<Record>,
    #[serde(default)]
    eligible_ids: Vec<String>,
    #[serde(default)]
    query: String,
    #[serde(default)]
    now: u64,
    #[serde(default = "budget")]
    budget: usize,
}
fn budget() -> usize {
    8192
}
fn run(r: Request) -> Result<Value, String> {
    if r.store_id.len() != 36
        || !r.store.is_absolute()
        || r.project_id.is_empty()
        || r.memory_key.is_empty()
        || r.project_id.len() > 160
        || r.memory_key.len() > 160
        || r.configuration_hash.len() != 64
    {
        return Err("explicit absolute store, scope and configuration hash required".into());
    }
    let binding = json!({"protocol":"adaptive-recalltree/2","project_id":r.project_id,
        "memory_key":r.memory_key,"configuration_hash":r.configuration_hash,"store_id":r.store_id});
    let marker = r.store.join("scope.binding");
    if r.operation == "init" {
        // Only create a NEW directory. Never reset or adopt an existing store.
        fs::create_dir(&r.store).map_err(|e| format!("fresh directory required: {e}"))?;
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&marker)
            .map_err(|e| e.to_string())?;
        file.write_all(serde_json::to_string(&binding).unwrap().as_bytes())
            .map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        return Ok(json!({"protocol":"adaptive-recalltree/2","status":"initialized","empty":true}));
    }
    if r.operation != "retain" && r.operation != "search" {
        return Err("unknown operation".into());
    }
    let actual: Value = serde_json::from_slice(
        &fs::read(marker).map_err(|_| "store unavailable or uninitialized")?,
    )
    .map_err(|e| e.to_string())?;
    if actual != binding {
        return Err("store scope/configuration mismatch".into());
    }
    let engine = Engine::open(r.store.join("generations"), Limits::default())?;
    if r.operation == "retain" {
        if r.run_id.is_empty() || r.records.is_empty() || r.records.len() > 33 {
            return Err("bounded run and records required".into());
        }
        let mut ids = BTreeSet::new();
        for record in &r.records {
            if record.scope != r.project_id
                || record.role != r.memory_key
                || record.applicability != r.configuration_hash
                || record.shared
                || record.status != "active"
                || !record.supersedes.is_empty()
                || !record.conflicts.is_empty()
                || record.kind != Kind::Interpretation
                || !ids.insert(record.id.clone())
            {
                return Err("record scope/kind/identity mismatch".into());
            }
        }
        let state = engine.state();
        if state.runs.contains(&r.run_id) {
            if r.records
                .iter()
                .any(|record| state.records.get(&record.id) != Some(record))
            {
                return Err("retained run identity conflict".into());
            }
        } else {
            for record in r.records {
                engine.ingest(&r.run_id, record, b"")?;
            }
            engine.finalize(&r.run_id, Fault::None)?;
        }
        Ok(
            json!({"protocol":"adaptive-recalltree/2","status":"retained","run_id":r.run_id,"record_ids":ids}),
        )
    } else {
        if r.query.len() > 2000 || !(256..=32768).contains(&r.budget) || r.eligible_ids.len() > 32 {
            return Err("search budget exceeded".into());
        }
        let mut state = engine.state();
        let allowed: BTreeSet<_> = r.eligible_ids.into_iter().collect();
        // Apply the host's current admission set before ranking or omission disclosure.
        state.records.retain(|id, record| {
            allowed.contains(id)
                && record.scope == r.project_id
                && record.role == r.memory_key
                && record.applicability == r.configuration_hash
        });
        let missing: Vec<_> = allowed
            .iter()
            .filter(|id| !state.records.contains_key(*id))
            .cloned()
            .collect();
        let packet = retrieve(
            &state,
            &r.memory_key,
            &r.project_id,
            &r.query,
            r.now,
            r.budget,
        )?;
        Ok(
            json!({"protocol":"adaptive-recalltree/2","status":if missing.is_empty(){"ok"}else{"partial"},"packet":packet,"missing_ids":missing}),
        )
    }
}
fn main() {
    let result = (|| -> Result<Value, String> {
        let mut data = Vec::new();
        io::stdin()
            .take(65537)
            .read_to_end(&mut data)
            .map_err(|e| e.to_string())?;
        if data.len() > 65536 {
            return Err("request exceeds 64 KiB".into());
        }
        let request = serde_json::from_slice(&data).map_err(|e| e.to_string())?;
        run(request)
    })();
    match result {
        Ok(value) => println!("{}", value),
        Err(error) => {
            println!(
                "{}",
                json!({"protocol":"adaptive-recalltree/2","status":"error","error":error})
            );
            std::process::exit(1);
        }
    }
}
