import unittest
from adaptive_agents import Assignment, Lifecycle, Store
from adaptive_agents.adapters import ScopedMessages

class MessageIdentityTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(':memory:')
        self.life=Lifecycle(self.store,lambda:1000)
        self.messages=ScopedMessages(self.life)
        self.ids=[]
        for name in ('A','B','C'):
            spec=self.life.allocate(Assignment('assignment','project',name,'Check fixture','Reviewer'))
            self.ids.append(spec['instance_id'])
            self.life.transition(spec['instance_id'],'running')
    def tearDown(self): self.store.close()

    def test_recipient_message_id_collision_rejected_without_side_effects(self):
        a,b,c=self.ids
        first=self.messages.send(a,c,'one',message_id='m1')
        before=len(self.store.events())
        with self.assertRaisesRegex(ValueError,'recipient message identity conflict'):
            self.messages.send(b,c,'two',message_id='m1')
        self.assertEqual(len(self.store.events()),before)
        second=self.messages.send(b,c,'two',message_id='m2')
        ack1=self.messages.acknowledge(c,'m1')
        ack2=self.messages.acknowledge(c,'m2')
        self.assertNotEqual(ack1,ack2)
        acked={e['payload']['message_event_id'] for e in self.store.events(c) if e['type']=='message_ack'}
        self.assertEqual(acked,{first,second})

    def test_legacy_collision_requires_explicit_sender(self):
        a,b,c=self.ids
        first=self.messages.send(a,c,'one',message_id='legacy')
        spec,_,_=self.life._load(b)
        # Simulate the immutable records already accepted by v0.1.0.
        second=self.store.append(spec,'message',{'message_id':'legacy','target_instance_id':c,'text':'two'},1000)
        with self.assertRaisesRegex(ValueError,'ambiguous message identity'):
            self.messages.acknowledge(c,'legacy')
        for sender,event in ((a,first),(b,second)):
            ack=self.messages.acknowledge(c,'legacy',source_instance_id=sender)
            self.assertEqual(ack,self.messages.acknowledge(c,'legacy',source_instance_id=sender))
            row=next(e for e in self.store.events(c) if e['event_id']==ack)
            self.assertEqual(row['payload']['message_event_id'],event)
        with self.assertRaises(ValueError): self.messages.acknowledge(c,'legacy',source_instance_id=c)

    def test_sender_retry_and_identical_text_other_sender(self):
        a,b,c=self.ids
        first=self.messages.send(a,c,'same',message_id='shared')
        count=len(self.store.events())
        self.assertEqual(first,self.messages.send(a,c,'same',message_id='shared'))
        with self.assertRaises(ValueError): self.messages.send(b,c,'same',message_id='shared')
        self.assertEqual(len(self.store.events()),count)

if __name__=='__main__': unittest.main()
