# Reproducible mechanical evaluation

Run cargo test --locked and cargo run --locked --example evaluate. The fixture builds 24 synthetic observations with two roles and explicit shared visibility. At five exact JSON byte budgets it compares local/shared and unified role-filtered packets under identical candidate eligibility, query, ordering and serializer. Serialized bytes must be identical. Equality is stricter than equal hashes and avoids introducing a cryptographic dependency.

The CSV reports budget, selected count, full serialized byte count and equality. This is a contract/budget simulator, not an LLM benchmark. No real-world speed, emergent intelligence, formal fractality, factual recall improvement or validated self-improvement is established. Evidence references are synthetic and marked unavailable.

Tests cover escaped Unicode, full envelope costs, role/scope and expiry, supersession, provenance/kind preservation, capacity fail-stop, candidate sharing rejection, duplicate IDs, concurrent finalize, working memory bounds, precommit and cleanup failure, postcommit replay and reopening after a committed interruption. Fault injection covers specified code boundaries; it is not an exhaustive power-loss/filesystem test.

Before claiming learning benefits, compare against a same-budget baseline on a preregistered held-out task set with independently scored factual outcomes, provenance correctness, leakage, total cost and regressions. Promotion should record evaluation artifact links and applicability, and disagreements must remain auditable.
