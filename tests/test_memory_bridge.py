import hashlib
import pathlib
import tempfile
import unittest
from adaptive_agents import Assignment, Lifecycle, Store
from adaptive_agents.memory import AgentSearch, RecallTreeMemory, MemoryUnavailable

EXE=pathlib.Path(__file__).resolve().parents[1]/'rust/recalltree-bridge/target/debug/adaptive-recalltree-bridge.exe'
if not EXE.exists(): EXE=EXE.with_suffix('')

@unittest.skipUnless(EXE.exists(),'build optional RecallTree bridge first')
class MemoryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.tmp.name)
        self.store=Store(':memory:'); self.now=1000
        self.life=Lifecycle(self.store,lambda:self.now)
        self.memory=self.adapter()
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def adapter(self,**changes):
        args=dict(executable=EXE,executable_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),
                  directory=self.root/'fresh',project_id='project',memory_key='reviewer',configuration_hash='a'*64)
        args.update(changes)
        return RecallTreeMemory(self.life,**args)
    def instance(self,**changes):
        args=dict(assignment_id='task',project_id='project',job_name='Field Auditor',objective='Inspect fixture',role='Review',
                  template_id='reviewer',configuration_hash='a'*64,lesson_keys=('schema',))
        args.update(changes)
        return self.life.allocate(Assignment(**args))['instance_id']
    def lesson(self):
        instance=self.instance()
        self.life.transition(instance,'running')
        outcome=self.life.transition(instance,'completed',summary='Synthetic check',evidence=[{'ref':'fixture://outcome','sha256':'b'*64}])
        verifier=self.life.verify(instance,passed=True,verifier='host-v1',evidence_event_id=outcome,check='independent fixture assertion')
        self.life.add_lesson(instance,key='schema',text='Check required schema fields',verification_event_id=verifier,expires_at=1100)
        return instance,verifier
    def test_empty_and_unavailable_are_distinct(self):
        instance=self.instance()
        self.assertEqual(self.memory.search(instance,'schema')['status'],'unavailable')
        self.assertFalse(self.memory.directory.exists())
        self.memory.initialize()
        result=self.memory.search(instance,'schema')
        self.assertEqual(result['status'],'ok'); self.assertEqual(result['packet']['records'],[])
    def test_initialize_never_adopts_existing_directory(self):
        self.memory.directory.mkdir()
        sentinel=self.memory.directory/'original.txt'; sentinel.write_text('preserve')
        with self.assertRaises(MemoryUnavailable): self.memory.initialize()
        self.assertEqual(sentinel.read_text(),'preserve')
    def test_real_retrieval_provenance_and_retirement(self):
        self.memory.initialize(); source,verifier=self.lesson()
        receipt=self.memory.retain(source,artifact_retention_ack='host-artifacts')
        self.memory.retire(source,artifact_retention_ack='host-artifacts')
        self.assertNotIn(source,self.life.contexts)
        target=self.instance(assignment_id='next-task')
        result=AgentSearch(self.memory).search(target,'schema')
        records=result['memory']['packet']['records']
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['kind'],'interpretation')
        self.assertEqual(records[0]['evidence'][0]['uri'],'verification:'+verifier)
        event=self.store.events(target)[-1]
        self.assertEqual(event['type'],'memory_retrieval')
        self.assertEqual(event['payload']['selected_count'],1)
        self.assertIsNone(event['payload']['execution_cost'])
        self.assertNotIn('query',event['payload'])
        self.assertEqual(self.store.events(source)[-1]['payload']['retention_ack'],receipt)
    def test_cross_project_configuration_and_identity_rejected(self):
        self.memory.initialize()
        for changes in ({'project_id':'other'},{'configuration_hash':'c'*64},{'template_id':'other'}):
            instance=self.instance(**changes)
            with self.assertRaises(ValueError): self.memory.search(instance,'schema')
    def test_revocation_excludes_retained_memory_without_deleting(self):
        self.memory.initialize(); source,verifier=self.lesson()
        self.memory.retain(source,artifact_retention_ack='retained')
        before=list((self.memory.directory/'generations').glob('*.json'))
        self.life.revoke_verification(source,verifier,reason='fixture corrected')
        target=self.instance(assignment_id='next')
        result=self.memory.search(target,'schema')
        self.assertEqual(result['packet']['records'],[])
        self.assertEqual(before,list((self.memory.directory/'generations').glob('*.json')))
    def test_expiry_excludes_retained_memory(self):
        self.memory.initialize(); source,_=self.lesson(); self.memory.retain(source,artifact_retention_ack='retained')
        self.now=1100
        self.assertEqual(self.memory.search(self.instance(),'schema')['packet']['records'],[])
    def test_failed_backend_retention_keeps_context(self):
        source,_=self.lesson()
        with self.assertRaises(MemoryUnavailable): self.memory.retire(source,artifact_retention_ack='retained')
        self.assertIn(source,self.life.contexts)
        self.assertFalse(any(e['type']=='retired' for e in self.store.events(source)))
    def test_retention_retry_and_missing_records(self):
        self.memory.initialize(); source,_=self.lesson()
        target=self.instance()
        self.assertEqual(self.memory.search(target,'schema')['status'],'partial')
        receipt=self.memory.retain(source,artifact_retention_ack='retained')
        count=len(self.store.events())
        self.assertEqual(receipt,self.memory.retain(source,artifact_retention_ack='retained'))
        self.assertEqual(count,len(self.store.events()))
        with self.assertRaises(ValueError): self.memory.retain(source,artifact_retention_ack='changed')
    def test_unverified_outcome_not_searchable(self):
        self.memory.initialize(); source=self.instance(); self.life.transition(source,'running')
        self.life.transition(source,'completed',summary='worker claims success')
        self.memory.retain(source,artifact_retention_ack='retained')
        self.assertEqual(self.memory.search(self.instance(),'success')['packet']['records'],[])
    def test_source_search_callback_receives_host_scope(self):
        self.memory.initialize(); calls=[]
        search=AgentSearch(self.memory,lambda project,query: calls.append((project,query)) or {'status':'ok','results':[]})
        search.search(self.instance(),'schema')
        self.assertEqual(calls,[('project','schema')])
        with self.assertRaises(ValueError): search.search(self.instance(project_id='other'),'schema')
        self.assertEqual(len(calls),1)
    def test_executable_tamper_or_wrong_store_binding_unavailable(self):
        self.memory.initialize()
        wrong=self.adapter(executable_sha256='0'*64)
        self.assertEqual(wrong.search(self.instance(),'schema')['status'],'unavailable')
        binding=self.memory.directory/'scope.binding'
        binding.write_text('{}')
        self.assertEqual(self.memory.search(self.instance(),'schema')['status'],'unavailable')

    def test_receipt_append_failure_keeps_context_and_retry_recovers(self):
        from unittest.mock import patch
        self.memory.initialize(); source,_=self.lesson()
        with patch.object(self.store,'append',side_effect=OSError('synthetic journal failure')):
            with self.assertRaises(OSError): self.memory.retire(source,artifact_retention_ack='retained')
        self.assertIn(source,self.life.contexts)
        self.assertFalse(any(e['type']=='retired' for e in self.store.events(source)))
        self.memory.retire(source,artifact_retention_ack='retained')
        self.assertNotIn(source,self.life.contexts)

    def test_tampered_provenance_is_not_admitted(self):
        from unittest.mock import patch
        self.memory.initialize(); source,_=self.lesson(); self.memory.retain(source,artifact_retention_ack='retained')
        target=self.instance(); original=self.memory._call
        def altered(operation,**payload):
            response=original(operation,**payload)
            response['packet']['records'][0]['evidence'][0]['uri']='verification:forged'
            return response
        with patch.object(self.memory,'_call',side_effect=altered):
            result=self.memory.search(target,'schema')
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(self.store.events(target)[-1]['payload']['selected'],[])

    def test_graph_associations_and_structural_privacy(self):
        self.memory.initialize(); source,_=self.lesson(); self.memory.retain(source,artifact_retention_ack='retained')
        target=self.instance(); self.memory.search(target,'schema')
        graph=self.store.graph()
        kinds={edge['type'] for edge in graph['edges']}
        self.assertTrue({'retrieved_for_run','retained_in_memory'} <= kinds)
        self.assertNotIn('Check required schema fields',str(self.store.export_structure(target)))

if __name__=='__main__': unittest.main()
