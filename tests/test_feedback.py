import unittest
import test_lifecycle
from adaptive_agents import Assignment
from adaptive_agents.feedback import Feedback, utility, summarize
from adaptive_agents.adapters import ScopedMessages

class FeedbackTests(unittest.TestCase):
    setUp = test_lifecycle.LifecycleTests.setUp
    tearDown = test_lifecycle.LifecycleTests.tearDown
    allocate = test_lifecycle.LifecycleTests.allocate
    completed = test_lifecycle.LifecycleTests.completed
    def pair(self, name="case-1", **overrides):
        instance,outcome=self.completed()
        verifier=self.life.verify(instance,passed=True,verifier="independent-host",evidence_event_id=outcome,check="paired fixture evaluation")
        args=dict(trial_id=name,key="schema",candidate_version="candidate-v1",verification_event_id=verifier,
                  baseline=dict(verified_success=False,execution_cost=0.2,verification_cost=0.2),
                  candidate=dict(verified_success=True,execution_cost=0.4,verification_cost=0.2),expires_at=1100)
        args.update(overrides)
        feedback=Feedback(self.life)
        feedback.record(instance,**args)
        return feedback,instance,args
    def choose(self, feedback, **kwargs):
        return feedback.select("project","schema","candidate-v1",case_ids=["case-1"],minimum=1,**kwargs)
    def test_coverage_trap(self):
        unknown=dict(verified_success=None,execution_cost=0,verification_cost=0)
        success=dict(unknown,verified_success=True)
        a=summarize([success]+[unknown]*9); b=summarize([success]*8+[unknown]*2)
        self.assertEqual(a["conditional_success"],1)
        self.assertLess(a["credited_success"],b["credited_success"])
    def test_cost_monotonicity_unknown_and_missing(self):
        self.assertLess(utility(True,0.5,0),utility(True,0,0))
        self.assertEqual(utility(None,0,0),0)
        self.assertEqual(utility(False,0,0),0)
        self.assertIsNone(utility(True,None,0))
        self.assertIsNone(summarize([])["coverage"])
    def test_gate_duplicate_and_revision(self):
        feedback,instance,args=self.pair()
        eid=feedback.record(instance,**args)
        self.assertEqual(self.choose(feedback)["n"],1)
        self.assertEqual(self.choose(feedback)["decision"],"candidate")
        args.update(revision=2,candidate=dict(args["baseline"]))
        self.assertNotEqual(eid,feedback.record(instance,**args))
        self.assertEqual(self.choose(feedback)["n"],1)
        self.assertEqual(self.choose(feedback)["decision"],"baseline")
    def test_missing_cost_and_safety_veto(self):
        for override in ({"safety_passed":False},{"candidate":dict(verified_success=True,execution_cost=None,verification_cost=0)}):
            feedback,_,_=self.pair(name=str(len(self.store.events())),**override)
            name=self.store.events()[-1]["payload"]["trial_id"]
            self.assertEqual(feedback.select("project","schema","candidate-v1",case_ids=[name],minimum=1)["decision"],"baseline")
    def test_scope_version_expiry_and_incomplete(self):
        feedback,_,_=self.pair()
        self.assertEqual(self.choose(feedback,environment_version="changed")["decision"],"baseline")
        self.assertEqual(feedback.select("other","schema","candidate-v1",case_ids=["case-1"],minimum=1)["decision"],"baseline")
        self.assertEqual(feedback.select("project","schema","candidate-v1",case_ids=["case-1","missing"],minimum=1)["decision"],"baseline")
        self.now=1100
        self.assertEqual(self.choose(feedback)["decision"],"baseline")
    def test_evidence_revocation_invalidates_feedback(self):
        feedback,instance,args=self.pair()
        self.life.revoke_verification(instance,args["verification_event_id"],reason="artifact hash changed")
        self.assertEqual(self.choose(feedback)["decision"],"baseline")
    def test_idempotent_transition_and_retirement(self):
        instance=self.allocate()
        a=self.life.transition(instance,"running",operation_id="start")
        self.assertEqual(a,self.life.transition(instance,"running",operation_id="start"))
        with self.assertRaises(ValueError): self.life.transition(instance,"failed",operation_id="start")
        self.life.transition(instance,"cancelled")
        a=self.life.retire(instance,retention_ack="retained")
        self.assertEqual(a,self.life.retire(instance,retention_ack="retained"))
    def test_messages_budget_dedup_scope_and_export(self):
        a,b=self.allocate(),self.allocate()
        self.life.transition(a,"running"); self.life.transition(b,"running")
        messages=ScopedMessages(self.life,max_messages=1)
        eid=messages.send(a,b,"Only task data",message_id="msg-1")
        self.assertEqual(eid,messages.send(a,b,"Only task data",message_id="msg-1"))
        with self.assertRaises(ValueError): messages.send(a,b,"too many",message_id="msg-2")
        other=self.life.allocate(Assignment("other","project","Other job","objective","role"))["instance_id"]
        self.life.transition(other,"running")
        with self.assertRaises(ValueError): messages.send(a,other,"leak",message_id="msg-3")
        export=self.store.export_structure(a,limit=1)
        self.assertTrue(export["truncated"])
        self.assertNotIn("payload",export["events"][0])

    def test_one_trial_per_instance_and_rebuild(self):
        feedback,instance,args=self.pair()
        changed=dict(args,trial_id="different")
        with self.assertRaises(ValueError): feedback.record(instance,**changed)
        recovered=Feedback(type(self.life)(self.store,lambda:self.now))
        self.assertEqual(self.choose(feedback),self.choose(recovered))
    def test_allocation_and_verify_retry(self):
        assignment=Assignment("task","project","Auditor","Check","Role")
        a=self.life.allocate(assignment,operation_id="allocation")
        b=self.life.allocate(assignment,operation_id="allocation")
        self.assertEqual(a["instance_id"],b["instance_id"])
        instance,outcome=self.completed()
        args=dict(passed=True,verifier="host",evidence_event_id=outcome,check="bound check",operation_id="verify")
        self.assertEqual(self.life.verify(instance,**args),self.life.verify(instance,**args))
    def test_configuration_scope(self):
        instance,outcome=self.completed()
        verification=self.life.verify(instance,passed=True,verifier="host",evidence_event_id=outcome,check="bound check")
        self.life.add_lesson(instance,key="schema",text="Check fields",verification_event_id=verification,expires_at=1100)
        self.assertEqual(self.store.lessons("project",["schema"],1000,configuration_hash="a"*64),[])
    def test_permission_invariance(self):
        class Host:
            def discover_tools(self,project): return ["read","write","message"]
            def request_tool(self,instance,tool,args): return {"allowed":tool=="read"}
        host=Host()
        feedback,instance,args=self.pair()
        before=host.request_tool(instance,"write",{})
        self.assertEqual(self.choose(feedback)["decision"],"candidate")
        self.assertEqual(before,host.request_tool(instance,"write",{}))
        self.assertFalse(before["allowed"])
    def test_message_ack(self):
        a,b=self.allocate(),self.allocate()
        self.life.transition(a,"running"); self.life.transition(b,"running")
        messages=ScopedMessages(self.life)
        messages.send(a,b,"bounded data",message_id="message-ack")
        self.assertEqual(messages.acknowledge(b,"message-ack"),messages.acknowledge(b,"message-ack"))
    def test_generator_evidence_validated(self):
        instance=self.allocate(); self.life.transition(instance,"running")
        with self.assertRaises(ValueError): self.life.transition(instance,"completed",evidence=(x for x in [{"ref":"bad","sha256":"bad"}]))

if __name__=="__main__": unittest.main()
