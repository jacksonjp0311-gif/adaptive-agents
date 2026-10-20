# Adversarial review — v0.1

A separate local review pass after implementation inspected verifier authority, duplicate/replay paths, evidence iteration, retirement ordering, scope filters, trial revision rebuilding, export omissions and package contents. No external reviewer or live-harness evaluation was used.

Findings fixed before release:

- Generator evidence was consumed before validation. Validation now checks the captured payload list; a regression test passes malformed generator evidence.
- Multiple case IDs could inflate a single instance's trial contributions. A run now owns one trial identity, with explicit revisions.
- Lesson scope lacked configuration provenance. Exact configuration-hash matching now supplements project/key and expiry/revocation.
- Duplicate operation retries needed explicit identities. Allocation, transitions and verification now accept operation_id; retirement and messages have dedicated receipt/message identity checks.
- A weak synthetic baseline alone could mislead. The benchmark now also includes an equal-capability no-memory baseline and reports its retained-baseline outcome.

Boundaries intentionally retained:

- Verification is a host-only trust interface. This library cannot authenticate arbitrary callers, inspect private artifacts, enforce OS permissions, or detect forged evaluator claims. Never expose its admission methods directly to an agent.
- A host retention ACK is an attestation, not a filesystem durability audit. Host must retain/check evidence before calling retire.
- SQLite triggers prevent ordinary updates/deletes, not privileged database tampering. Protect the storage boundary.
- Serialize operations per scope through the host controller; concurrent arbitrary admission/message/retrieval writers are not certified. Transitions alone use explicit database transactions.
- Full graph export contains private payloads. The bounded structural projection omits them; host must still redact opaque IDs where sensitive.

Remaining evidence gaps: actual Pegasus wiring, model behavior, external tool brokers, hard process deadlines, representative task gains and independent human review.


## v0.1.1 independent findings and patch review

A separate parent-provided source reviewer identified two concrete defects in commit 34fc85849142167c0fb7008df31326f476c3555f: cross-sender message ID collisions made recipient ACK ambiguous, and current expiry/revocation checks rejected exact historical trial retries. Both were reproduced before code edits. Original failing outputs are retained in `docs/regressions/` with the local workspace path redacted; the baseline source remains in Git history.

The patch review checked that collisions have no step/event side effects, original-sender retries stay idempotent, legacy ambiguous records fail explicitly and can be selected by sender, unauthorized recipients cannot ACK another message, and historical trial retries neither create contributions nor restore revoked/expired evidence. Changed stale payloads still fail admission and old-revision retries do not roll back current selection. Seven added cases pass; full suite is 37 tests. No model or live harness was invoked.


## v0.2 memory implementation review

A separate post-implementation review pass checked persistence ordering, scope admission, backend trust, runtime bounds and source provenance. It added exact equality checks for retrieved evidence/version/kind fields, explicit malformed-response rejection, and regression cases for forged provenance, receipt-journal failure with recovery, and graph/structural-export separation. This was a self-review pass; independent review of the new memory adapter remains pending with the integrating host.

All 21 vendored source files match the pinned public upstream Git blob hashes after line-ending normalization. The publication allowlist excludes build targets, synthetic runtime stores, private Pegasus integration code and live data. RecallTree's existing license decision is unchanged and explicitly excluded from root MIT. The owner authorized source publication; this is not a new public copyright license.

Validation: 51 Python tests passed, including 14 actual local bridge tests with no skips; upstream Rust tests passed (15 integration tests), formatting and clippy warnings-as-errors passed, and its synthetic evaluation ran offline. The 0.2.0 wheel built without downloading dependencies; isolated import includes memory.py, and CLI demo/export returned valid JSON. Actual outputs accompany the release. The Rust bridge had already built and passed clippy offline before the final Python tests.

Known limits: optional memory support is opt-in; core retirement alone does not enforce this backend. A successful retention receipt is historical and does not re-audit disk availability on retry. If eligibility changes after a backend commit but before receipt journaling, reconciliation is required. Scope/configuration markers and binary hashes do not defeat a privileged local attacker. One serial controller and host-protected paths remain required. Memory search is bounded lexical retrieval, not learned ranking. No live model, Pegasus UI, causal quality improvement or production deployment was tested.


## v0.2.1 independent review corrections

Parent-provided independent review found scope filtering after the 32-lesson cap and retention receipt reuse across destination stores. Both were reproduced against v0.2.0 before implementation changes; failing outputs are preserved in docs/regressions/v020-memory-*.txt with local paths redacted. A related overflow case also reproduced incomplete retention success.

Selection now applies project/key/configuration plus source/template filters before limiting. Retention checks 33 eligible records to detect overflow and fails before backend writes or retirement when completeness cannot fit. Search stays capped after template admission. Receipt reuse requires matching store UUID/destination digest; a different directory or replacement UUID cannot reuse the receipt. Legacy markers and unbound receipts require explicit host reconciliation; no old memory is changed. Optional bridge wire protocol is v2, while lifecycle envelope v1 is unchanged.

Six new regression cases pass, bringing the full suite to 57 tests (20 actual bridge tests, no skips). Existing identical retention retry and journal-failure recovery tests still pass. Offline bridge build/clippy, baseline benchmark, wheel build, isolated import and CLI JSON roundtrip passed. Vendored upstream source remains byte-identical after normalized line endings. No live harness or private memory was touched.
