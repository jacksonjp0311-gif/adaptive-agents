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
