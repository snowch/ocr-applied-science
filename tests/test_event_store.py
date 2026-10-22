import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from app.event_store import CorruptEvent, EventConflict, EventStore

class EventStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=EventStore(self.temp.name)
    def test_retry_returns_original_timestamp_and_bytes(self):
        identifier=str(uuid.uuid4());payload={'outcome':'hint'}
        event=self.store.append(identifier,'answer_observed',payload)
        path=Path(self.temp.name)/(identifier+'.json');before=path.read_bytes()
        self.store.clock=lambda:dt.datetime(2030,1,1,tzinfo=dt.timezone.utc)
        self.assertEqual(self.store.append(identifier,'answer_observed',payload),event)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(len(self.store.all()),1)
    def test_concurrent_identical_retries_publish_one_complete_event(self):
        identifier=str(uuid.uuid4())
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            events=list(pool.map(lambda _:self.store.append(identifier,'answer_observed',{'outcome':'independent'}),range(36)))
        self.assertTrue(all(e==events[0] for e in events))
        self.assertEqual(len(self.store.all()),1)
        self.assertEqual(list(self.store.staging.iterdir()),[])
    def test_conflicting_retry_never_overwrites(self):
        identifier=str(uuid.uuid4())
        before=self.store.append(identifier,'answer_observed',{'outcome':'hint'})
        with self.assertRaises(EventConflict):self.store.append(identifier,'answer_observed',{'outcome':'independent'})
        self.assertEqual(self.store.get(identifier),before)
    def test_corrupt_payload_fails_instead_of_disappearing_from_progress(self):
        identifier=str(uuid.uuid4());event=self.store.append(identifier,'answer_observed',{'outcome':'hint'})
        event['payload']['outcome']='independent'
        (Path(self.temp.name)/(identifier+'.json')).write_text(json.dumps(event))
        with self.assertRaises(CorruptEvent):self.store.all()
    def test_incomplete_staging_file_is_not_read_as_an_observation(self):
        self.store.initialise();(self.store.staging/'incomplete').write_text('{')
        self.assertEqual(self.store.all(),[])
    def test_path_traversal_identifier_is_rejected(self):
        with self.assertRaises(ValueError):self.store.append('../outside','answer_observed',{})

if __name__=='__main__':unittest.main()
