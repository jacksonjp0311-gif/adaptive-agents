"""Deterministic finite-case demonstration, not an agent-quality evaluation."""
import hashlib
import json
from adaptive_agents import Assignment, Lifecycle, Store
from adaptive_agents.feedback import Feedback, summarize

# Frozen synthetic holdout: fields required by eight different job schemas.
CASES = tuple((f"case-{i}", {"name": "synthetic"}, f"required_{i}") for i in range(8))

def run():
    store=Store(":memory:")
    life=Lifecycle(store,lambda:1000)
    feedback=Feedback(life)
    outcomes={"baseline":[],"candidate":[],"strong_baseline":[]}
    # Independently approved training evidence supplies a scoped general recipe.
    seed=life.allocate(Assignment("training","synthetic-project","Required Field Reviewer","Review field presence","Schema reviewer"))["instance_id"]
    life.transition(seed,"running")
    outcome=life.transition(seed,"completed",evidence=[{"ref":"fixture://training","sha256":hashlib.sha256(b'validate declared required field').hexdigest()}])
    verification=life.verify(seed,passed=True,verifier="fixture-evaluator-v1",evidence_event_id=outcome,check="Training recipe matches schema requirement")
    life.add_lesson(seed,key="required-fields-v1",text="Check the field declared required by this schema",verification_event_id=verification,expires_at=1100)
    life.retire(seed,retention_ack="synthetic-retention")
    for case_id, document, required in CASES:
        spec=life.allocate(Assignment(case_id,"synthetic-project","Field Contract Auditor","Check fixture","Schema reviewer",lesson_keys=("required-fields-v1",)))
        instance=spec["instance_id"]
        life.transition(instance,"running")
        # Baseline is intentionally simple: fixed 'name' check, no retrieved recipe.
        baseline_valid="name" in document
        candidate_valid=required in document if spec["lessons"] else baseline_valid
        expected_valid=required in document
        baseline=dict(verified_success=baseline_valid==expected_valid,execution_cost=0.1,verification_cost=0.1)
        candidate=dict(verified_success=candidate_valid==expected_valid,execution_cost=0.2,verification_cost=0.1)
        receipt=json.dumps({"case":case_id,"baseline":baseline,"candidate":candidate},sort_keys=True).encode()
        result=life.transition(instance,"completed",evidence=[{"ref":"fixture://"+case_id,"sha256":hashlib.sha256(receipt).hexdigest()}])
        verified=life.verify(instance,passed=True,verifier="fixture-evaluator-v1",evidence_event_id=result,check="Compare both outputs to frozen required-field oracle")
        feedback.record(instance,trial_id=case_id,key="required-fields-v1",candidate_version="scoped-recipe-v1",verification_event_id=verified,baseline=baseline,candidate=candidate,expires_at=1100,suite_version="required-fields-v1")
        life.retire(instance,retention_ack="synthetic-retention")
        outcomes["baseline"].append(baseline); outcomes["candidate"].append(candidate)
        strong=dict(verified_success=(required in document)==expected_valid,execution_cost=0.1,verification_cost=0.1)
        outcomes["strong_baseline"].append(strong)
        strong_instance=life.allocate(Assignment("strong-"+case_id,"synthetic-project","Equal Capability Comparison","Evaluate direct schema check","Independent evaluator"))["instance_id"]
        life.transition(strong_instance,"running")
        strong_receipt=json.dumps({"case":case_id,"baseline":strong,"candidate":candidate},sort_keys=True).encode()
        result=life.transition(strong_instance,"completed",evidence=[{"ref":"fixture://strong-"+case_id,"sha256":hashlib.sha256(strong_receipt).hexdigest()}])
        verified=life.verify(strong_instance,passed=True,verifier="fixture-evaluator-v1",evidence_event_id=result,check="Equal-capability no-memory schema check against same oracle")
        feedback.record(strong_instance,trial_id="strong-"+case_id,key="required-fields-strong-v1",candidate_version="scoped-recipe-v1",verification_event_id=verified,baseline=strong,candidate=candidate,expires_at=1100,suite_version="required-fields-v1")
        life.retire(strong_instance,retention_ack="synthetic-retention")
    result={"fixture_suite":"required-fields-v1","synthetic_only":True,"baseline":summarize(outcomes["baseline"]),"candidate":summarize(outcomes["candidate"]),"gate":feedback.select("synthetic-project","required-fields-v1","scoped-recipe-v1",case_ids=[x[0] for x in CASES],suite_version="required-fields-v1")}
    result["strong_baseline"]=summarize(outcomes["strong_baseline"])
    result["strong_comparison"]=feedback.select("synthetic-project","required-fields-strong-v1","scoped-recipe-v1",case_ids=["strong-"+x[0] for x in CASES],suite_version="required-fields-v1")
    result["strong_comparison"].pop("trial_event_ids")
    # Event IDs are intentionally fresh; omit them from reproducible aggregate output.
    result["gate"].pop("trial_event_ids")
    store.close()
    return result

if __name__ == "__main__": print(json.dumps(run(),indent=2))
