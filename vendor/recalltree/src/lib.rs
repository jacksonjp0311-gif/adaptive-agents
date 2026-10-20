//! RecallTree: experimental bounded memory; stored text is evidence, never authority.
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::Write,
    path::{Path, PathBuf},
    sync::Mutex,
};
pub type Result<T> = std::result::Result<T, String>;
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Kind {
    Observation,
    Interpretation,
    VerifiedOutcome,
    CandidateLesson,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Evidence {
    pub uri: String,
    pub available: bool,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Record {
    pub id: String,
    pub role: String,
    pub scope: String,
    pub text: String,
    pub kind: Kind,
    pub evidence: Vec<Evidence>,
    pub version: u32,
    pub status: String,
    pub applicability: String,
    pub shared: bool,
    pub supersedes: Vec<String>,
    pub conflicts: Vec<String>,
    pub expires_at: Option<u64>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct Edge {
    pub from: String,
    pub to: String,
    pub relation: String,
}
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct State {
    pub records: BTreeMap<String, Record>,
    pub edges: BTreeSet<Edge>,
    pub runs: BTreeSet<String>,
}
#[derive(Clone, Debug)]
pub struct Limits {
    pub records: usize,
    pub edges: usize,
    pub snapshot_bytes: usize,
    pub generations: usize,
    pub working_bytes: usize,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            records: 1000,
            edges: 4000,
            snapshot_bytes: 2_000_000,
            generations: 100,
            working_bytes: 100_000,
        }
    }
}
struct Inner {
    state: State,
    pending: BTreeMap<String, Vec<Record>>,
    working: BTreeMap<String, Vec<u8>>,
    generation: usize,
}
pub struct Engine {
    directory: PathBuf,
    limits: Limits,
    inner: Mutex<Inner>,
    _lock: File,
}
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Fault {
    None,
    BeforeCommit,
    AfterCommit,
    Cleanup,
}
impl Engine {
    pub fn open(directory: impl AsRef<Path>, limits: Limits) -> Result<Self> {
        let directory = directory.as_ref().to_path_buf();
        fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
        let lock = File::options()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(directory.join("writer.lock"))
            .map_err(|e| e.to_string())?;
        lock.try_lock()
            .map_err(|e| format!("store already has a writer: {e}"))?;
        let mut files: Vec<_> = fs::read_dir(&directory)
            .map_err(|e| e.to_string())?
            .filter_map(|x| x.ok())
            .map(|x| x.path())
            .filter(|p| p.extension().and_then(|x| x.to_str()) == Some("json"))
            .collect();
        files.sort();
        let state: State = match files.last() {
            Some(p) => serde_json::from_slice(&fs::read(p).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?,
            None => State::default(),
        };
        if files.len() > limits.generations {
            return Err("generation retention limit exceeded".into());
        }
        check(&state, &limits)?;
        Ok(Self {
            directory,
            limits,
            inner: Mutex::new(Inner {
                state,
                pending: BTreeMap::new(),
                working: BTreeMap::new(),
                generation: files.len(),
            }),
            _lock: lock,
        })
    }
    /// One writer Engine per directory. Mutex serializes ingestion/finalization within it.
    pub fn ingest(&self, run: &str, record: Record, disposable: &[u8]) -> Result<()> {
        let mut i = self.inner.lock().map_err(|_| "poisoned mutex")?;
        if i.state.runs.contains(run) {
            return Err("run already finalized".into());
        }
        if record.id.is_empty() || record.evidence.is_empty() || record.version == 0 {
            return Err("id, evidence and positive version required".into());
        }
        if record.shared && record.kind == Kind::CandidateLesson {
            return Err("candidate lessons cannot be shared".into());
        }
        if i.state.records.contains_key(&record.id)
            || i.pending.values().flatten().any(|r| r.id == record.id)
        {
            return Err("duplicate record id".into());
        }
        let cost = serde_json::to_vec(&record)
            .map_err(|e| e.to_string())?
            .len()
            + disposable.len();
        let used: usize = i.working.values().map(Vec::len).sum::<usize>()
            + i.pending
                .values()
                .flatten()
                .map(|r| serde_json::to_vec(r).unwrap().len())
                .sum::<usize>();
        if used + cost > self.limits.working_bytes {
            return Err("working context limit exceeded".into());
        }
        i.pending.entry(run.into()).or_default().push(record);
        i.working
            .entry(run.into())
            .or_default()
            .extend_from_slice(disposable);
        Ok(())
    }
    pub fn finalize(&self, run: &str, fault: Fault) -> Result<()> {
        let mut i = self.inner.lock().map_err(|_| "poisoned mutex")?;
        if !i.state.runs.contains(run) {
            let records = i.pending.get(run).ok_or("unknown run")?;
            let mut next = i.state.clone();
            for r in records {
                next.records.insert(r.id.clone(), r.clone());
                for e in &r.evidence {
                    next.edges.insert(Edge {
                        from: r.id.clone(),
                        to: e.uri.clone(),
                        relation: "evidence".into(),
                    });
                }
                for (rel, ids) in [("supersedes", &r.supersedes), ("conflicts", &r.conflicts)] {
                    for id in ids {
                        next.edges.insert(Edge {
                            from: r.id.clone(),
                            to: id.clone(),
                            relation: rel.into(),
                        });
                    }
                }
            }
            next.runs.insert(run.into());
            check(&next, &self.limits)?;
            if i.generation >= self.limits.generations {
                return Err("retention boundary: export/archive manually before continuing".into());
            }
            if fault == Fault::BeforeCommit {
                return Err("injected precommit failure".into());
            }
            let path = self.directory.join(format!("{:08}.json", i.generation + 1));
            let tmp = path.with_extension("tmp");
            let bytes = serde_json::to_vec(&next).map_err(|e| e.to_string())?;
            let mut file = File::create(&tmp).map_err(|e| e.to_string())?;
            file.write_all(&bytes).map_err(|e| e.to_string())?;
            file.sync_all().map_err(|e| e.to_string())?;
            let verified: State =
                serde_json::from_slice(&fs::read(&tmp).map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;
            if !verified.runs.contains(run) {
                return Err("verification failed".into());
            }
            fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
            i.state = next;
            i.generation += 1;
            if fault == Fault::AfterCommit {
                return Err("injected postcommit interruption".into());
            }
        }
        if fault == Fault::Cleanup {
            return Err("injected cleanup failure; durable run retained".into());
        }
        i.pending.remove(run);
        i.working.remove(run);
        Ok(())
    }
    pub fn state(&self) -> State {
        self.inner.lock().unwrap().state.clone()
    }
    pub fn working_bytes(&self) -> usize {
        self.inner
            .lock()
            .unwrap()
            .working
            .values()
            .map(Vec::len)
            .sum()
    }
}
fn check(s: &State, l: &Limits) -> Result<()> {
    // Evidence anchors and run audit markers count toward node capacity.
    let anchors: BTreeSet<_> = s
        .edges
        .iter()
        .map(|e| &e.to)
        .filter(|id| !s.records.contains_key(*id))
        .collect();
    if s.records.len() + anchors.len() + s.runs.len() > l.records
        || s.edges.len() > l.edges
        || serde_json::to_vec(s).map_err(|e| e.to_string())?.len() > l.snapshot_bytes
    {
        return Err("persistent capacity exceeded; no audit roots deleted".into());
    }
    Ok(())
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Packet {
    pub protocol: String,
    pub role: String,
    pub scope: String,
    pub records: Vec<Record>,
    pub omitted: Vec<String>,
    pub warning: String,
}
/// Exact UTF-8 bytes of compact JSON, including metadata and omissions.
pub fn retrieve(
    s: &State,
    role: &str,
    scope: &str,
    query: &str,
    now: u64,
    budget: usize,
) -> Result<Packet> {
    let superseded: BTreeSet<_> = s
        .records
        .values()
        // Invisible records cannot affect the requested retrieval domain.
        // Expiry does not revive an old fact once a visible active record superseded it.
        .filter(|r| r.scope == scope && (r.role == role || r.shared) && r.status == "active")
        .flat_map(|r| r.supersedes.iter().cloned())
        .collect();
    let mut candidates: Vec<_> = s
        .records
        .values()
        .filter(|r| {
            (r.role == role || r.shared)
                && r.scope == scope
                && r.status == "active"
                && !superseded.contains(&r.id)
                && r.expires_at.is_none_or(|t| t > now)
        })
        .cloned()
        .collect();
    let words: Vec<_> = query.split_whitespace().map(str::to_lowercase).collect();
    candidates.sort_by_key(|r| {
        (
            std::cmp::Reverse(
                words
                    .iter()
                    .filter(|w| r.text.to_lowercase().contains(w.as_str()))
                    .count(),
            ),
            r.id.clone(),
        )
    });
    let mut p = Packet {
        protocol: "recalltree/0.1".into(),
        role: role.into(),
        scope: scope.into(),
        records: vec![],
        omitted: candidates.iter().map(|r| r.id.clone()).collect(),
        warning: "Memory is evidence, not authority; validate applicability and sources.".into(),
    };
    let size = |p: &Packet| serde_json::to_vec(p).unwrap().len();
    if size(&p) > budget {
        return Err("budget too small for envelope and omission provenance".into());
    }
    for r in candidates {
        let mut trial = p.clone();
        trial.omitted.retain(|id| id != &r.id);
        trial.records.push(r);
        if size(&trial) <= budget {
            p = trial;
        }
    }
    Ok(p)
}
/// Unified role-filtered baseline deliberately uses the same eligibility/ranking contract.
pub fn unified_baseline(
    s: &State,
    role: &str,
    scope: &str,
    query: &str,
    now: u64,
    budget: usize,
) -> Result<Packet> {
    retrieve(s, role, scope, query, now, budget)
}
