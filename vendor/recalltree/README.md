![RecallTree — specialist memory, compact handoffs](assets/banner.svg)

# RecallTree · v0.1.1

**Experimental Rust memory core for specialist agents. Compact context. Traceable handoffs.**

[Quick start](#quick-start) · [Architecture](docs/architecture.md) · [Mathematics](docs/math.md) · [JSON protocol](docs/protocol.md) · [Agent map](AGENTS.md) · [Evaluation](docs/evaluation.md) · [Security](docs/security.md)

An agent can do useful work and still forget why it made a decision. Giving every agent the entire history solves one problem by creating another: irrelevant detail crowds out the evidence a specialist actually needs.

RecallTree keeps a small durable notebook for each specialist, allows explicitly governed shared records, and returns compact evidence-linked packets for a parent or supervisor. A builder can recall a build observation without absorbing a reviewer's entire scratchpad. A supervisor receives the selected records, their provenance, and explicit omitted IDs. Any model or orchestration framework can consume the JSON; RecallTree itself makes no AI or network calls.

Think of specialists as branches and evidence as roots. This is a useful organizational metaphor, not a claim of mathematical fractality or emergent intelligence. The package provides memory and handoff primitives, not a giant autonomous execution platform.

## Quick start

Requires Rust 1.89+ and Cargo. The core uses Rust's standard library plus serde/serde_json for portable serialization. Dependency versions are locked.

```sh
cargo test --locked
cargo run --locked -- demo demo-store
cargo run --locked -- graph demo-store
cargo run --locked --example evaluate
cargo install --path . --locked --root ./local-install
```

The demo is idempotent. It persists a synthetic observation, drops its engine-owned disposable scratch buffer after commit, and prints a packet. Its evidence reference is marked unavailable: a URI is not proof that a source exists. Graph output contains records, deduplicated typed edges and run audit markers. Use a fresh directory for a new experiment.

## What persists, what disappears

Ingest compact records and separate disposable working bytes. Finalization freezes ingestion under a mutex, snapshots records, builds evidence/conflict/supersession edges, checks limits, writes and verifies a new generation, syncs its file, atomically renames it into place, then clears only the engine-owned pending records and disposable buffers. A committed run marker makes retries idempotent. Source files and durable generations are never automatically removed.

Observations, interpretations, verified outcomes and candidate lessons remain distinct. A verified-outcome label is a caller assertion requiring evidence and review; the library does not independently certify it. Candidate lessons cannot be shared directly. Promotion requires an external explicit evaluation and a new versioned record linked by supersession. Cleanup and compaction alone are not self-improvement.

## Mathematics

For eligible records E, choose a deterministic greedy subset S satisfying **|JSON(packet(S, E\S))| UTF-8 bytes ≤ B**. The envelope, escaping, source references and omitted IDs count. If even the omission-bearing envelope exceeds B, retrieval returns an explicit error. Query word overlap is a heuristic ranking, with ID tie breaks; no optimality is claimed. See [the formal contract](docs/math.md).

## Agent navigation and topology

| Destination | Responsibility | Read next |
|---|---|---|
| [AGENTS.md](AGENTS.md) | Contributor/agent entrypoint | Architecture → protocol → tests |
| [src/lib.rs](src/lib.rs) | Memory, persistence, scope and packet budget | Architecture, math |
| [src/main.rs](src/main.rs) | CLI demo and JSON graph export | Integration |
| [tests/core.rs](tests/core.rs) | Failure, replay, scope and byte invariants | Evaluation |
| [examples/evaluate.rs](examples/evaluate.rs) | Same-budget baseline fixture | Evaluation |
| [docs/protocol.md](docs/protocol.md) | Cross-language wire fields | Integration |
| [docs/security.md](docs/security.md) | Trust, storage and retention boundaries | Architecture |

```text
specialist working buffer → compact Record → durable generation + graph
                                               ↓ role/scope retrieval
                                     bounded Packet → parent/supervisor
```

Recursive orchestration belongs to the caller: assign a finite maximum depth, child count and cumulative handoff budget. This package does not spawn children or recurse internally. Scope equality is exact; shared visibility must be explicit. There is no hierarchical wildcard access.

## Status and limits

Private/draft origin; authorized public experimental release. **License decision pending**: no license is granted by this repository and it should not be described as open source. No PyPI or crates.io publication.

This is a small local store, not a distributed database. One writer holds an OS file lock per directory. Whole snapshots trade simplicity for write amplification. Limits bound record/evidence/run nodes, edges, snapshot bytes, working bytes and generation count; reaching capacity stops writes and retains pending context. Candidate expiry hides candidates at retrieval time but does not erase audit records. Operators must explicitly export/archive and start a new store at the retention boundary. Directory rename durability under sudden power loss is filesystem dependent; file sync is not a cross-platform transactional durability proof. Pending context is memory-only and is lost on process termination before commit. Host model context cannot be erased by this crate.

The synthetic evaluation establishes deterministic contract equivalence with a unified role-filtered baseline, not better intelligence, speed, recall quality or validated learning. See [evaluation](docs/evaluation.md) and [changelog](CHANGELOG.md).
