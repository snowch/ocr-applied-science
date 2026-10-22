"""Check the shared record through two independent HTTP clients."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import uuid
from app import server
from app.event_store import EventStore

class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        server.STORE=EventStore(Path(cls.temp.name)/'initial');server.initialise()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.http.server_port)
        cls.parent=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.student=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.temp.cleanup()
    def setUp(self):
        server.STORE=EventStore(Path(self.temp.name)/str(uuid.uuid4()));server.initialise()
    def request(self,client,path,body=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with client.open(req) as response:return json.load(response)
    def answer(self,**overrides):
        return {'id':str(uuid.uuid4()),'question_id':'F181-P01','variant':'main','mode':'parent','outcome':'independent','hints':0,'student_saw_answer':False,'answer':'Explains why; describes what.','note':'Clear explanation.',**overrides}
    def test_parent_record_visible_to_student_and_survives_reopen(self):
        body=self.answer();self.request(self.parent,'/api/attempts',body)
        state=self.request(self.student,'/api/state')
        self.assertEqual(state['total_attempts'],1)
        self.assertEqual(state['recent'][0]['mode'],'parent')
        server.initialise()
        self.assertEqual(self.request(self.student,'/api/state')['total_attempts'],1)
    def test_retry_does_not_double_count_and_changed_payload_rejected(self):
        body=self.answer()
        self.request(self.parent,'/api/attempts',body);self.request(self.parent,'/api/attempts',body)
        self.assertEqual(self.request(self.student,'/api/state')['total_attempts'],1)
        with self.assertRaises(urllib.error.HTTPError) as error:self.request(self.parent,'/api/attempts',{**body,'note':'Different'})
        self.assertEqual(error.exception.code,400)
    def test_hints_and_revealed_answers_cannot_be_independent(self):
        for override in [{'hints':1},{'student_saw_answer':True}]:
            saved=self.request(self.parent,'/api/attempts',self.answer(**override))
            self.assertEqual(saved['outcome'],'hint')
    def test_one_good_answer_and_same_day_repetition_do_not_establish_retention(self):
        self.request(self.parent,'/api/attempts',self.answer())
        self.request(self.student,'/api/attempts',self.answer(mode='self',variant='retest'))
        q=self.request(self.student,'/api/state')['questions'][next(i for i,q in enumerate(server.BANK['questions']) if q['id']=='F181-P01')]
        self.assertFalse(q['later_retest'])
    def test_later_retest_counts_then_new_difficulty_takes_precedence(self):
        past=dt.datetime.now(server.UTC)-dt.timedelta(days=2)
        server.STORE.clock=lambda:past
        first=self.answer();self.request(self.parent,'/api/attempts',first)
        original=(server.STORE.directory/(first['id']+'.json')).read_bytes()
        server.STORE.clock=lambda:dt.datetime.now(server.UTC)
        self.request(self.parent,'/api/attempts',self.answer(variant='retest'))
        self.assertTrue(self.request(self.student,'/api/state')['questions'][next(i for i,q in enumerate(server.BANK['questions']) if q['id']=='F181-P01')]['later_retest'])
        latest=self.answer(outcome='practice');self.request(self.parent,'/api/attempts',latest)
        q=self.request(self.student,'/api/state')['questions'][next(i for i,q in enumerate(server.BANK['questions']) if q['id']=='F181-P01')]
        self.assertFalse(q['later_retest']);self.assertEqual(q['status'],'practice')
        self.request(self.parent,'/api/undo',{'id':latest['id']})
        self.assertTrue(self.request(self.student,'/api/state')['questions'][next(i for i,q in enumerate(server.BANK['questions']) if q['id']=='F181-P01')]['later_retest'])
        self.assertEqual((server.STORE.directory/(first['id']+'.json')).read_bytes(),original)
        self.assertEqual(len(server.STORE.all()),4)
    def test_invalid_question_and_cross_origin_write_are_rejected(self):
        for body,origin,code in [(self.answer(question_id='other'),None,400),(self.answer(),'https://unrelated.example',403)]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.request(self.parent,'/api/attempts',body,origin)
            self.assertEqual(error.exception.code,code)

if __name__=='__main__':unittest.main(verbosity=2)
