# Mathematics of bounded feedback — v0.1

This is an implemented accounting model and finite-suite decision rule, not a new learning theorem. Code lives in `adaptive_agents/feedback.py`. The adapted object is an immutable, versioned task recipe or a validated context lesson. Model weights are never updated. Fresh agent names identify instances; they are not recipe IDs or independent statistical samples.

## 1. What earns credit

For each launched run i, let e_i be 1 only when an authorized evaluator supplies usable verification, and 0 otherwise. Let y_i be binary verified success when e_i=1. Unknown outcomes have no y_i and receive zero positive credit, without being relabeled verified failures.

r_i = e_i y_i

u_i = r_i - 0.25 c_i - 0.25 v_i

Here c_i and v_i are execution and verification budget fractions in [0,1]. Units, denominators, evaluator rubric, environment/tool/model versions and normalization must be frozen before comparing recipes. Values outside this range are rejected. A missing cost is `None`, and utility is unavailable, never silently zero. `utility(None, c, v)` gives no success credit; `utility(False, c, v)` records a known failure with the same numerical reward but different evidence status. Worker self-reports cannot call the trusted evaluator interface.

The coefficients are fixed in `verified-utility-v1`. Changing them requires a new policy version and new comparable evidence. Costs normalized to different budgets cannot be pooled under the same environment/suite version.

## 2. Coverage prevents selective-success claims

For N launched outcomes, q = sum(e_i)/N and mu = sum(r_i)/sum(e_i), when their denominators exist. Define credited success as sum(r_i)/N, with value 0 if all outcomes are unknown and N>0. For N=0 metrics are unavailable.

J = sum(u_i)/N = q mu - 0.25 mean(c) - 0.25 mean(v)

The identity follows by cancelling sum(e_i), when it is nonzero. It is accounting, not a causal estimate. One verified success out of ten launches has conditional success 100% but credited success 10%; eight verified successes out of ten have credited success 80%. `summarize` includes every supplied launched outcome; the host must supply all launches, not a selected success-only sample. v0.1 does not automatically join arbitrary host execution logs.

Increasing costs by nonnegative dc,dv changes utility by -0.25 dc -0.25 dv <= 0, for fixed credited outcome. This proves cost monotonicity for the implemented function, not optimal behavior.

## 3. Scoped evidence and deterministic updates

A paired trial carries project, recipe key, candidate version, policy version, rubric version, environment version, frozen suite version, unique trial ID, revision, expiry, safety verdict, bound verification event, and both arms' outcomes/costs. The environment version must fingerprint tool/model/sandbox configuration; the core treats it as an opaque host identifier. The verification event binds the instance and durable outcome artifact digests. The host authenticates the verifier and checks artifact bytes; a hash string alone cannot prove truth.

The journal is append-only. For each project and trial ID, rebuild uses only the latest revision. Identical retries return the existing historical event even after expiry, revocation or later revisions; this acknowledges past storage without revalidation or changing the latest contribution. changed payloads require exactly the next revision and the original owning instance. A later correction can remove earlier credit. Revoking the supporting verification excludes the trial and its lessons. Expired or version-mismatched evidence remains historical evidence but is inapplicable to the current gate. No cross-project evidence is selected.

Under the documented single-controller contract, the unique latest-revision map has at most one contribution per trial ID, so replaying identical records cannot inflate n. No claim is made about a hostile caller editing SQLite files or unsafely concurrent feedback writers.

## 4. Generation, evaluation and promotion are different

Generation creates a candidate recipe or scoped lesson. Evaluation uses an independently approved verifier on fixed cases, budgets, environment and rubric. Promotion is only a host decision after the gate recommendation; `select` never deploys a recipe or changes permission.

For frozen paired cases j, define d_j = u_candidate,j - u_baseline,j. The default finite-suite gate requires:

1. Every frozen case has current, correctly scoped evidence and complete costs/outcomes.
2. All safety/permission checks pass, and n >= minimum (default 8).
3. Mean(d) > margin (default 0); ties retain the baseline.
4. Every d_j >= -epsilon (default epsilon=0).

These conditions prove only the checked finite-suite inequalities. With epsilon=0, no included case regresses under this utility. They do not imply population improvement, statistical significance, general intelligence, or that the next task benefits. Adaptive reuse of the same suite can overfit; keep a separate untouched evaluation set and version new experiments. Ordinary observational averages can guide investigation but cannot call this paired gate without the frozen case set and evidence.

No probability bound, bandit, gradient update or automatic production rollout is implemented. The code intentionally has one feedback model.

## 5. Authority and retirement invariants

Allowed(call) = HostPolicy(call, current authority, current context).

Names, rewards, graph edges, lessons and peer messages do not occur as authority-granting inputs. The core has no tool executor; hosts discover all connected tools and decide each requested action under existing permissions and confirmations. The protocol alone cannot prove a third-party host obeys this contract.

Retirement requires a persisted terminal outcome and a host evidence-retention ACK. A failed journal write preserves this library's context reference and leaves retirement pending. External context disposal follows the successful commit. The durable evidence is not deleted. Peer messages stay within one project and assignment, with bounded content/count and execution-step charging; communication never delegates permission.

## 6. Reproduce the finite demonstration

```sh
python -m unittest discover -s tests -v
python -m examples.benchmark
```

`required-fields-v1` contains eight synthetic schema cases, a fixed no-memory baseline checking `name`, and a candidate applying a validated required-field recipe. Both are compared with a frozen field-presence oracle. Declared cost fractions are synthetic constants, not measured runtime costs. Saved outputs are in [BENCHMARK.json](BENCHMARK.json) and [TEST-RESULTS.txt](TEST-RESULTS.txt).

The construction deliberately favors the candidate and shows that the lifecycle, evidence selection and finite gate work together. It is not a representative task sample or a claim of improved LLM performance. The included equal-capability no-memory baseline directly checks the declared field: it matches candidate correctness with lower declared cost, and the strong-comparison gate retains the baseline. Retrieval is not proven necessary. No model calls occur.

## 7. Hypotheses and falsifiers

- Deduplication: identical trial ingestion cannot increase n. Falsified by a replay increasing the selected case count.
- Scope: changing an unrelated project's evidence cannot affect this project's selection. Falsified by any changed gate result.
- Coverage: unknown launches cannot earn positive credit. Falsified by `None` increasing credited success.
- Cost sensitivity: increasing a cost cannot increase utility. Falsified by any allowed numerical counterexample.
- Finite no-regression: with epsilon=0, a candidate selected despite a negative case delta falsifies the gate.
- Future quality improvement remains an unverified hypothesis requiring representative, prospectively frozen model/harness trials. A degraded holdout result refutes a proposed promotion even if the synthetic fixture passes.

## 8. Sources and limits of attribution

[Reflexion (Shinn et al., 2023)](https://arxiv.org/abs/2303.11366) studies linguistic feedback and episodic memory rather than weight updates. It motivates the distinction; its benchmark results are not results of this module.

[Generalization in Adaptive Data Analysis and Holdout Reuse (Dwork et al., 2015)](https://proceedings.neurips.cc/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html) motivates caution about adaptive holdout reuse. This implementation does not implement that paper's algorithms or inherit its guarantees.

[Concrete Problems in AI Safety (Amodei et al., 2016)](https://arxiv.org/abs/1606.06565) discusses reward hacking, supervision and distribution shift. These concerns motivate independent evaluation and explicit applicability rules; this module does not solve them generally.
