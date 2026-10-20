"""Verified credited utility and a finite-suite promotion gate; no weight training."""
import math
from .core import ident

POLICY_VERSION = "verified-utility-v1"

def utility(verified_success, execution_cost, verification_cost):
    """None is unknown, False is verified failure. Missing cost stays unavailable."""
    if verified_success is not None and type(verified_success) is not bool:
        raise ValueError("success must be host-verified bool or None")
    for cost in (execution_cost, verification_cost):
        if cost is not None and (type(cost) not in (int, float) or not math.isfinite(cost) or not 0 <= cost <= 1):
            raise ValueError("cost must be normalized to [0,1] or None")
    if execution_cost is None or verification_cost is None: return None
    return int(verified_success is True) - 0.25 * execution_cost - 0.25 * verification_cost

def summarize(outcomes):
    outcomes=list(outcomes)
    n=len(outcomes)
    evaluable=sum(x["verified_success"] is not None for x in outcomes)
    credit=sum(x["verified_success"] is True for x in outcomes)
    values=[utility(**x) for x in outcomes]
    return {"launches":n,"evaluable":evaluable,"coverage":evaluable/n if n else None,
            "conditional_success":credit/evaluable if evaluable else None,
            "credited_success":credit/n if n else None,
            "mean_utility":sum(values)/n if n and all(v is not None for v in values) else None}

class Feedback:
    """Host-only evaluator interface. One serial controller owns trial updates."""
    def __init__(self, lifecycle): self.life = lifecycle

    def record(self, instance, *, trial_id, key, candidate_version, verification_event_id,
               baseline, candidate, expires_at, rubric_version="v1", environment_version="v1",
               suite_version="v1", safety_passed=True, revision=1):
        for value in (trial_id,key,candidate_version,rubric_version,environment_version,suite_version): ident(value)
        if type(revision) is not int or revision < 1 or type(safety_passed) is not bool: raise ValueError("invalid revision/safety")
        spec, _, events = self.life._load(instance)
        bu,cu=utility(**baseline),utility(**candidate)
        payload = {"trial_id":trial_id,"key":key,"candidate_version":candidate_version,
                   "policy_version":POLICY_VERSION,"rubric_version":rubric_version,
                   "environment_version":environment_version,"suite_version":suite_version,
                   "verification_event_id":verification_event_id,"revision":revision,"safety_passed":safety_passed,
                   "baseline":dict(baseline),"candidate":dict(candidate),"expires_at":expires_at,
                   "delta":cu-bu if cu is not None and bu is not None else None}
        if any(e["type"]=="paired_trial" and e["payload"]["trial_id"]!=trial_id for e in events): raise ValueError("one trial identity per instance")
        previous=[e for e in self.life.store.events() if e["type"]=="paired_trial" and e["project_id"]==spec["project_id"] and e["payload"]["trial_id"]==trial_id]
        if previous:
            old=previous[-1]
            if old["instance_id"] != instance: raise ValueError("trial belongs to another instance")
            # Historical receipt lookup never revalidates or reapplies old evidence.
            identical=next((e for e in previous if e["payload"]==payload),None)
            if identical: return identical["event_id"]
            if revision != old["payload"]["revision"]+1: raise ValueError("revision must advance exactly once")
        elif revision != 1: raise ValueError("first revision must be 1")
        verification = next((e for e in events if e["event_id"] == verification_event_id and e["type"] == "verification"), None)
        if not verification or not verification["payload"]["passed"] or any(e["type"]=="verification_revoked" and e["payload"]["verification_event_id"]==verification_event_id for e in events):
            raise ValueError("independent evaluator must attest paired trial evidence")
        if type(expires_at) not in (int,float) or not math.isfinite(expires_at) or not self.life.clock() < expires_at <= self.life.clock()+2592000:
            raise ValueError("invalid trial expiry")
        return self.life.store.append(spec,"paired_trial",payload,self.life.clock())

    def select(self, project_id, key, candidate_version, *, case_ids, rubric_version="v1",
               environment_version="v1", suite_version="v1", minimum=8, margin=0.0, epsilon=0.0):
        if type(minimum) is not int or minimum < 1 or any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in (margin,epsilon)):
            raise ValueError("invalid gate parameters")
        if not case_ids or len(set(case_ids))!=len(case_ids): raise ValueError("frozen unique case IDs required")
        latest={}
        for e in self.life.store.events():
            if e["type"]=="paired_trial" and e["project_id"]==project_id:
                latest[e["payload"]["trial_id"]]=e
        invalid={e["payload"]["verification_event_id"] for e in self.life.store.events() if e["type"]=="verification_revoked"}
        trials=[]
        for case in case_ids:
            e=latest.get(case)
            if not e: continue
            p=e["payload"]
            if (p["key"],p["candidate_version"],p["policy_version"],p["rubric_version"],p["environment_version"],p["suite_version"]) != (key,candidate_version,POLICY_VERSION,rubric_version,environment_version,suite_version): continue
            if p["expires_at"]<=self.life.clock() or p["verification_event_id"] in invalid: continue
            trials.append(e)
        complete=len(trials)==len(case_ids) and len(trials)>=minimum
        usable=complete and all(e["payload"]["safety_passed"] and e["payload"]["delta"] is not None and all(e["payload"][arm]["verified_success"] is not None for arm in ("baseline","candidate")) for e in trials)
        mean=sum(e["payload"]["delta"] for e in trials)/len(trials) if usable else None
        promote=usable and mean>margin and all(e["payload"]["delta"]>=-epsilon for e in trials)
        return {"policy_version":POLICY_VERSION,"decision":"candidate" if promote else "baseline",
                "n":len(trials),"mean_delta":mean,"reason":"finite suite gate passed" if promote else "incomplete, unsafe, tied or insufficient finite-suite improvement",
                "trial_event_ids":[e["event_id"] for e in trials]}
