# Budget and selection mathematics

First define the visible domain V as records with exact scope and matching role or shared=true. Let E be active, unexpired records in V whose IDs are not superseded by any active record in V. Records outside V cannot influence supersession or omissions. Inactive replacements have no effect. Active supersession remains effective even after a visible superseding record expires: expiry does not revive outdated facts. Expiry is evaluated at caller-supplied epoch seconds.

Rank by descending count of query words contained in lowercase text, then ascending record ID. Repeated query words count repeatedly; this simple heuristic is not semantic retrieval. Visit each candidate once. Start with an empty selected set and all eligible IDs omitted. Accept a candidate only if compact JSON serialization of the entire trial Packet fits B UTF-8 bytes. The empty envelope must also fit. JSON escaping and non-ASCII bytes are included.

This greedy algorithm does not solve knapsack optimally and can skip long high-ranked records in favor of later small records. Approximate model tokens are never reported. v0.1 supports exact serialized bytes only; integrations may separately enforce a model tokenizer budget after wrapping the packet in a prompt.

For n eligible records, straightforward selection serializes up to n trial packets: worst-case quadratic payload work. Whole-state persistence is linear in stored payload. These are implementation bounds, not measured speed claims. Local/shared retrieval and unified role-filtered retrieval intentionally have identical E, ranking and serialization; their outputs must match byte for byte. A tree topology alone cannot create an advantage under identical candidates.
