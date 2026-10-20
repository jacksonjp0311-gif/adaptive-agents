# Integration

Use Engine::open(path, Limits), ingest(run, compact_record, disposable_bytes), finalize(run, Fault::None), then retrieve(state, role, scope, query, epoch_seconds, byte_budget). Cargo's library crate name is recalltree. See examples/evaluate.rs for complete Record construction.

The caller verifies outcomes and source availability, defines explicit scope authorization, assigns stable IDs, applies access policy and governs shared records. Store credentials nowhere in memory. A candidate lesson should remain local until regression and held-out evaluations support applicability. Promotion creates a separate reviewed record with a new ID/version and supersedes the candidate; audit roots remain intact. v0.1 contains no promotion or model training engine.

Recursive callers must set maximum depth, fanout, run count and total packet budget; forward a packet to the parent with the same provenance, not just its text. A finite topology is caller-managed. External model sessions may retain context after this crate clears buffers; use your provider's session lifecycle deliberately.

JSON makes the contract portable to Python, Rust and other runtimes. No language-specific model SDK or API is required. The CLI graph emits JSON for visualizers; do not confuse graph connectivity with truth.
