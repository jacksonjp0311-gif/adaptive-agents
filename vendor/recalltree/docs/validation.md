# v0.1.1 validation

Windows Rust 1.97: 15 integration tests pass, zero failures. Locked offline evaluation returns byte-identical packets at budgets 512, 1024, 2048, 4096 and 8192. Selected counts: 0, 2, 6, 13, 16. Full serialized bytes: 266, 812, 1909, 3841, 4672. Formatting and all-target clippy with denied warnings pass. CLI demo and graph, Cargo package verification and isolated installation are part of release validation.

CI repeats tests, evaluation, formatting and clippy on Windows and Linux. See the exact tagged commit's public workflow results for remote evidence. Local fixture outcomes do not establish LLM efficacy. Source ZIP validation checks Markdown relative targets and XML validity of the SVG banner.

Scope isolation regressions were reproduced as failures against v0.1.0 before applying the v0.1.1 correction.
