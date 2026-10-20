import unittest
import test_feedback

class HistoricalRetryTests(unittest.TestCase):
    setUp=test_feedback.FeedbackTests.setUp
    tearDown=test_feedback.FeedbackTests.tearDown
    allocate=test_feedback.FeedbackTests.allocate
    completed=test_feedback.FeedbackTests.completed
    pair=test_feedback.FeedbackTests.pair
    choose=test_feedback.FeedbackTests.choose

    def test_identical_trial_retry_after_expiry_is_historical_ack_only(self):
        feedback,instance,args=self.pair()
        original=feedback.record(instance,**args)
        count=len(self.store.events())
        self.now=1101
        self.assertEqual(feedback.record(instance,**args),original)
        self.assertEqual(len(self.store.events()),count)
        self.assertEqual(self.choose(feedback)['decision'],'baseline')

    def test_identical_trial_retry_after_revocation_is_historical_ack_only(self):
        feedback,instance,args=self.pair()
        original=feedback.record(instance,**args)
        self.life.revoke_verification(instance,args['verification_event_id'],reason='revoked fixture')
        count=len(self.store.events())
        self.assertEqual(feedback.record(instance,**args),original)
        self.assertEqual(len(self.store.events()),count)
        self.assertEqual(self.choose(feedback)['decision'],'baseline')

    def test_retry_old_revision_preserves_latest_selection(self):
        feedback,instance,args=self.pair()
        original=feedback.record(instance,**args)
        revision=dict(args,revision=2,candidate=dict(args['baseline']))
        feedback.record(instance,**revision)
        count=len(self.store.events())
        self.assertEqual(feedback.record(instance,**args),original)
        self.assertEqual(len(self.store.events()),count)
        self.assertEqual(self.choose(feedback)['decision'],'baseline')

    def test_changed_stale_payload_is_not_admitted(self):
        feedback,instance,args=self.pair()
        self.now=1101
        with self.assertRaises(ValueError): feedback.record(instance,**dict(args,revision=2))
        self.now=1000
        self.life.revoke_verification(instance,args['verification_event_id'],reason='revoked fixture')
        with self.assertRaises(ValueError): feedback.record(instance,**dict(args,revision=2,expires_at=1200))

if __name__=='__main__': unittest.main()
