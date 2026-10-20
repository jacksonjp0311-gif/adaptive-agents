# Maintainer and integration agent guidance

This repository owns a portable module only. Never edit an installed harness as a side effect of tests or packaging. Keep synthetic fixtures and runtime evidence separate. Do not commit databases, logs, credentials or real conversation context.

Read docs/INTEGRATION.md and docs/MATHEMATICS.md before changing behavior. Version public event/assignment contracts explicitly. Preserve outcome-before-retirement, host retention ACK, independent verification, scoped retrieval, unique trial identities and baseline fallback. Never expose verify/add_lesson/Feedback.record as unrestricted model tools. Tool discovery does not authorize execution. Scores cannot change permission decisions.

Run `python -m unittest discover -s tests -v`, `python -m examples.benchmark`, CLI demo/export, and offline packaging/import checks. Keep actual outputs under docs for a release. Review changes separately after implementation. Do not claim model quality gains from deterministic fixture tests. Use a new frozen suite/version for new experiments; host evidence must bind environment/tool/model versions and artifact hashes.
