# Changelog

## 0.2.0 - 2026-10-20

- Add optional fresh-store RecallTree bridge and Python memory adapter, with exact project/template/configuration binding.
- Retain terminal evidence before retirement; retrieve only currently validated, nonexpired, nonrevoked lessons.
- Add agent-search composition and provenance-linked retrieval telemetry; keep agent and memory policy evaluations separate.
- Vendor the public RecallTree v0.1.1 core unchanged with its original license decision and source/dependency manifests. No existing harness memory is imported.
- Add real offline subprocess integration tests, including failed retention, tampering, expiry and scope isolation.

## 0.1.1 - 2026-10-20

- Reject cross-sender message ID collisions for the same recipient before charging steps or appending events.
- Reject ambiguous legacy ACK lookup; optional source_instance_id selects the original sender without changing durable records.
- Acknowledge exact historical paired-trial retries after expiry, revocation or later revisions without admitting stale evidence or changing selection.
- Preserve original failing regression outputs and add seven focused regression cases. Full suite: 37 passing tests.

## 0.1.0 — 2026-10-20

- Initial portable standard-library lifecycle, job-specific names and fresh UUIDs.
- Append-only SQLite event graph, CopyRun linkage and bounded structural export.
- Evidence-bound host verification, retention ACK and safe context retirement.
- Scoped expiring/revocable lessons, bounded internal communication and host tool protocol.
- Verified credited utility and revision-aware finite-suite baseline comparison.
- Deterministic offline tests, synthetic benchmark, original SVG banner and integration documentation.

This release does not claim live-harness certification, weight training or general agent improvement.
