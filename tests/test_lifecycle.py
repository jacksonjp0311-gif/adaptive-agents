import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from adaptive_agents import Assignment, Lifecycle, Store

class MockHost:
    def __init__(self): self.calls = []
    def start(self, spec): self.calls.append(("start", spec["instance_id"]))
    def cancel(self, instance): self.calls.append(("cancel", instance))
    def dispose_context(self, instance): self.calls.append(("dispose", instance))

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name)/"events.sqlite")
        self.store = Store(self.path)
        self.now = 1000
        self.life = Lifecycle(self.store, lambda:self.now)
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def allocate(self, **kwargs):
        return self.life.allocate(Assignment("task", "project", "Schema Auditor", "Check schema", "Auditor", **kwargs))["instance_id"]
    def completed(self):
        instance = self.allocate()
        self.life.transition(instance,"running")
        outcome = self.life.transition(instance,"completed",evidence=[{"ref":"fixture://check", "sha256":"a"*64}])
        return instance, outcome
    def lesson(self):
        instance, outcome = self.completed()
        verified = self.life.verify(instance,passed=True,verifier="host",evidence_event_id=outcome,check="fixture assertion passed")
        lesson = self.life.add_lesson(instance,key="schema",text="Check required fields",verification_event_id=verified,expires_at=1100)
        return instance, lesson
    def test_fresh_identity_and_job_name(self):
        a,b=self.allocate(),self.allocate()
        self.assertNotEqual(a,b)
        self.assertNotEqual(self.life.contexts[a]["display_name"],self.life.contexts[b]["display_name"])
        self.assertEqual(self.life.contexts[a]["job_name"],self.life.contexts[b]["job_name"])
    def test_validation(self):
        for kwargs in ({"max_steps":0},{"timeout_seconds":float("nan")},{"requested_tools":"shell"},{"copy_run":{"unknown":"id"}}):
            with self.assertRaises(ValueError): self.allocate(**kwargs)
    def test_retirement_order(self):
        instance=self.allocate()
        with self.assertRaises(ValueError): self.life.retire(instance, retention_ack="host-retained-fixture")
        self.life.transition(instance,"cancelled")
        self.life.retire(instance, retention_ack="host-retained-fixture")
        self.assertNotIn(instance,self.life.contexts)
        self.assertEqual([e["type"] for e in self.store.events(instance)],["allocated","cancelled","retired"])
    def test_failure(self):
        instance=self.allocate(); self.life.transition(instance,"running")
        self.life.transition(instance,"failed",summary="mock failure"); self.life.retire(instance, retention_ack="host-retained-fixture")
        self.assertEqual(self.store.events(instance)[-2]["payload"]["summary"],"mock failure")
    def test_timeout(self):
        instance=self.allocate(timeout_seconds=2); self.life.transition(instance,"running")
        self.now+=2
        self.assertFalse(self.life.step(instance))
        self.assertEqual(self.store.events(instance)[-1]["type"],"timed_out")
    def test_budget(self):
        instance=self.allocate(max_steps=1); self.life.transition(instance,"running")
        self.assertTrue(self.life.step(instance)); self.assertFalse(self.life.step(instance))
    def test_duplicate_and_replay(self):
        instance=self.allocate(); recovered=Lifecycle(self.store)
        with self.assertRaises(ValueError): recovered.transition(instance,"running")
        self.life.transition(instance,"running")
        with self.assertRaises(ValueError): self.life.transition(instance,"running")
        self.life.transition(instance,"completed")
        with self.assertRaises(ValueError): self.life.transition(instance,"completed")
    def test_completion_is_not_verification(self):
        instance=self.allocate(); self.life.transition(instance,"running")
        outcome=self.life.transition(instance,"completed")
        with self.assertRaises(ValueError): self.life.verify(instance,passed=True,verifier="host",evidence_event_id=outcome,check="none")
        self.assertEqual(self.store.lessons("project",["schema"],self.now),[])
    def test_cross_task_evidence_rejected(self):
        a,outcome=self.completed(); b,_=self.completed()
        with self.assertRaises(ValueError): self.life.verify(b,passed=True,verifier="host",evidence_event_id=outcome,check="bad binding")
    def test_scoped_expiring_revocable_lessons(self):
        instance,lesson=self.lesson()
        self.assertEqual(len(self.store.lessons("project",["schema"],1000)),1)
        self.assertEqual(self.store.lessons("other",["schema"],1000),[])
        self.assertEqual(self.store.lessons("project",["other"],1000),[])
        self.assertEqual(self.store.lessons("project",["schema"],1100),[])
        self.life.revoke_lesson(instance,lesson)
        self.assertEqual(self.store.lessons("project",["schema"],1000),[])
    def test_failed_check_not_admitted(self):
        instance,outcome=self.completed()
        verified=self.life.verify(instance,passed=False,verifier="host",evidence_event_id=outcome,check="failed")
        with self.assertRaises(ValueError): self.life.add_lesson(instance,key="schema",text="unsafe",verification_event_id=verified,expires_at=1100)
    def test_append_only(self):
        self.allocate()
        for sql in ("DELETE FROM events","UPDATE events SET type='retired'"):
            with self.assertRaises(sqlite3.IntegrityError): self.store.db.execute(sql)
    def test_no_private_context_in_journal(self):
        self.allocate(context="PRIVATE_CONTEXT_SENTINEL")
        self.assertNotIn("PRIVATE_CONTEXT_SENTINEL",json.dumps(self.store.events()))
    def test_persistence_failure_keeps_context(self):
        instance,outcome=self.completed()
        original=self.store.append
        def fail(*args): raise OSError("disk unavailable")
        self.store.append=fail
        with self.assertRaises(OSError): self.life.retire(instance, retention_ack="host-retained-fixture")
        self.assertIn(instance,self.life.contexts)
        self.store.append=original
    def test_graph_and_mock_adapter(self):
        host=MockHost(); instance=self.allocate(copy_run={"run_id":"run-1","root_run_id":"root-1"})
        host.start(self.life.contexts[instance]); self.life.transition(instance,"running")
        host.cancel(instance); self.life.transition(instance,"cancelled"); self.life.retire(instance, retention_ack="host-retained-fixture"); host.dispose_context(instance)
        self.assertEqual([c[0] for c in host.calls],["start","cancel","dispose"])
        self.assertTrue(any(n["id"]=="copy_run:run-1" for n in self.store.graph()["nodes"]))
    def test_reopen_preserves_evidence(self):
        instance,_=self.completed(); self.life.retire(instance, retention_ack="host-retained-fixture")
        self.store.close(); self.store=Store(self.path)
        self.assertEqual(self.store.events(instance)[-1]["type"],"retired")

if __name__ == "__main__": unittest.main()
