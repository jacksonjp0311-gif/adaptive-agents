# Changelog

## 0.1.1

Fix retrieval scope isolation: only active superseding records visible to the requested exact scope and role/shared domain can hide records. Private records in another scope or role no longer suppress visible memories or their omission IDs. Add cross-scope, private-role, shared-role and inactive-status regressions. JSON protocol remains recalltree/0.1. The immutable v0.1.0 release is retained; use v0.1.1 for this correction.

## 0.1.0

Experimental Rust library and CLI, exact JSON byte budgets, scoped local/shared retrieval, provenance-linked graph, atomic generation finalization with disposable-context cleanup, bounded fail-stop retention and deterministic baseline evaluation. No model calls or validated learning claims. License pending.
