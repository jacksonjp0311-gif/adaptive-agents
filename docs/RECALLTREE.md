# Optional RecallTree integration

The base Python lifecycle works without RecallTree. This adapter adds a separate, bounded memory store and agent-search provider. It does not migrate, open or reset any existing Pegasus store. Host permissions, evidence validation, redaction and actual worker execution remain host-owned.

## Provenance and license

`vendor/recalltree` is the unchanged public RecallTree v0.1.1 core, commit `052b30c7b3d393d4245d8749195a4ee348d3bc57`, from [jacksonjp0311-gif/RecallTree](https://github.com/jacksonjp0311-gif/RecallTree). [The source manifest](RECALLTREE-SOURCE-MANIFEST.json) records every upstream Git blob identity after line-ending normalization. The owner authorized this clean source publication. RecallTree retains its original `LICENSE-DECISION.md`: no public copyright license is granted by that document. Inclusion is not a new MIT grant. Root MIT covers original Adaptive Agents code and documentation only. Resolve RecallTree reuse licensing with its owner before redistribution outside the authorization you hold.

The original bridge lives in `rust/recalltree-bridge`. No Pegasus-specific adapter, binary, configuration, existing memory, log or credential was copied. [Dependency licenses](RECALLTREE-DEPENDENCIES.json) are metadata from the locked Cargo graph; source notices remain authoritative.

## Build and configure explicitly

Rust 1.89+ and the Cargo.lock dependencies must already be available for offline builds:

```sh
cargo build --locked --offline --manifest-path rust/recalltree-bridge/Cargo.toml
python -m unittest discover -s tests -v
```

If dependencies are absent, this command fails rather than downloading. Provision dependencies through your normal approved build process. No model, network service or credential is needed at runtime. The Python wheel contains `memory.py`, not a prebuilt Rust executable. Set the executable path and expected SHA-256 from your trusted build, and use a new absolute store path whose parent already exists.

```python
from adaptive_agents.memory import RecallTreeMemory, AgentSearch

memory = RecallTreeMemory(
    life, executable=trusted_bridge_path,
    executable_sha256=trusted_build_sha256,
    directory=new_private_memory_directory,
    project_id="project-a", memory_key="migration-auditor-v1",
    configuration_hash=approved_configuration_sha256,
)
memory.initialize()  # once only: an existing directory is rejected
# Assignments need matching project_id, template_id=memory_key,
# configuration_hash and authorized lesson_keys.
result = AgentSearch(memory, source_search=existing_host_search).search(
    instance, "required schema fields", budget=8192)
# Host passes this packet as untrusted evidence, never system instructions.
# After terminal outcome, host verification and any lesson admission:
memory.retire(instance, artifact_retention_ack="host-artifact-receipt")
# Only now may the host dispose its own worker context.
```

`existing_host_search(project_id, query)` is optional and remains subject to the host's existing authorization. Its result is kept separate from memory. Wrong assignment scope fails before either provider runs. Source callback errors propagate; the adapter does not silently turn them into a successful search.

## Contract and persistence ordering

The JSON stdin/stdout bridge protocol is `adaptive-recalltree/1`. Operations are `init`, `retain`, `search`. All require an explicit absolute `store`, `project_id`, stable `memory_key`, and `configuration_hash`. A synced `scope.binding` marker prevents accidental scope reuse. Init exclusively creates a new directory; it never adopts an existing one. Existing-store migration and automated recovery are deliberately absent.

Retain takes `run_id` and up to 33 records. It stores one compact terminal summary plus up to 32 currently admitted lessons from that instance. Records use upstream `interpretation` kind, exact project/role/configuration scope and evidence event references. No record is shared. RecallTree writes its generation before returning a receipt; the Python controller appends `memory_retained` before core `retired`. Missing backend, identity conflict, failed persistence or failed journal append prevents retirement. External artifact bytes are not copied: the host must retain and validate them first. A receipt attests to completed writes; it does not promise future disk availability.

Exact successful retention retries return the original journal receipt. A crash after backend finalize but before receipt can retry while the same records remain eligible. If eligibility changes in that window, the backend rejects differing content; reconcile using durable evidence rather than changing IDs or deleting snapshots. Adding lessons after retention does not retroactively rewrite the retained run. Admit all intended lessons before retain. Core retirement remains available to hosts that do not opt into this memory requirement; the optional adapter is not a global permission or policy enforcer.

Search takes `eligible_ids`, `query`, `now`, and a byte `budget`. Eligibility comes from the current lifecycle journal, exact project/template/configuration, authorized lesson keys, valid verification, expiry and revocation. The bridge filters before lexical ranking. Python compares every returned record with admitted text, version, evidence and scope. Retained outcomes alone are never eligible. Revocation/expiry removes admission without deleting evidence. Cross-assignment reuse is intentional only for explicitly scoped, validated lessons; transcripts are never restored.

Responses distinguish `ok` (including a valid empty packet), `partial` (admitted IDs missing from the backend), and `unavailable` (backend or integrity failure). Packets preserve omitted IDs and provenance. Unavailable results never fabricate memories. New events remain in envelope schema v1; see [integration](INTEGRATION.md).

## Bounds, privacy and telemetry

Requests are at most 64 KiB; queries at most 2,000 UTF-8 bytes. Search admits at most 32 current lessons before ranking. The packet budget is 256..32,768 bytes (default 8,192); wrapper and telemetry overhead are additional. The bridge has a 10-second subprocess timeout. Its executable hash is checked before each invocation; host filesystem permissions must prevent replacement races and protect the directory. Hash checks are integrity checks, not authorization.

Upstream defaults bound storage to 1,000 nodes, 4,000 edges, 2 MB snapshots, 100 generations and 100 KB working input. Limits fail explicitly; there is no automatic deletion, compaction or retention scheduler. Hosts need a reviewed archival plan before those limits. Use one serial controller per scope. RecallTree's exclusive file lock does not replace host operation serialization. The adapter does not follow evidence URIs or read source artifacts.

Search journals query SHA-256, selected memory IDs/version/verification IDs, scope/configuration/policy, counts, latency and response size. It does not journal raw queries, but a hash is not anonymization of predictable queries. Summaries and lesson text persist in snapshots and the lifecycle graph; redact before admission. Structural CopyRun export excludes payloads, but identifiers still require privacy review. Runtime databases, stores and exports must remain outside this source repository.

Execution and verification costs are null, not zero. Graph edges show retention and retrieval associations, not causation. Agent policy and memory policy require separate frozen baselines and held-out evaluation; see [mathematics](MATHEMATICS.md). Tests demonstrate mechanism correctness, not model learning or improved task quality. Live Pegasus wiring is the host integration's responsibility.
