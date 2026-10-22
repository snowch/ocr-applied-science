import json
from pathlib import Path
import unittest
from app.learning import project
from app.assessment import validate
import datetime as dt
ROOT=Path(__file__).resolve().parent.parent
BANK=json.loads((ROOT/'content/exam-question-bank.json').read_text())
class ExamBankTests(unittest.TestCase):
    def test_scope_and_rubrics(self):
        qs=BANK['questions'];self.assertEqual(len(qs),460);self.assertEqual(len({q['id'] for q in qs}),len(qs));self.assertEqual(len({q['question'] for q in qs}),len(qs))
        self.assertEqual({q['unit'] for q in qs},{'F180','F181'})
        self.assertEqual(len(BANK['syllabus']['areas']),15)
        for a in BANK['syllabus']['areas']:
            for ref in a['references']:self.assertGreater(ref['practice_items'],0,(a['id'],ref['id']))
        lookup={q['id']:q for q in qs}
        for q in qs:
            with self.subTest(q=q['id']):
                self.assertEqual(sum(p['marks'] for p in q['marking_points']),q['max_marks'])
                self.assertEqual(len({p['id'] for p in q['marking_points']}),len(q['marking_points']))
                self.assertNotEqual(q['question'],q['retest']['question'])
                self.assertEqual(sum(p['marks'] for p in q['retest']['marking_points']),q['retest']['max_marks'])
                self.assertTrue(q['model_answer'] and q['hints'] and q['common_misconception'])
                if q['retest']['item_key'] in lookup:self.assertEqual(q['retest']['question'],lookup[q['retest']['item_key']]['question'])
    def test_preserved_pilot_ids(self):
        old=json.loads((ROOT/'content/f181-question-bank.json').read_text());lookup={q['id']:q for q in BANK['questions']}
        for q in old['questions']:
            self.assertEqual(lookup[q['id']]['question'],q['question']);self.assertEqual(lookup[q['id']]['marking_points'],q['marking_points'])
    def test_numerical_answer_spot_checks(self):
        cases={'Microscopy practical':'600','Relative atomic mass':'10.8','Titration endpoints':'23.62','Combustion calorimetry':'-630','Work done at an angle':'50 J','Ultrasound echoes':'0.060 m','Effective half-life':'2 hours','Quantitative interpretation':'25%'}
        for skill,expected in cases.items():
            q=next(q for q in BANK['questions'] if q['skill']==skill and q['demand']=='Application')
            self.assertIn(expected,q['model_answer'])
    def test_local_server_secure_policy_and_reopened_gap(self):
        qs=BANK['questions'][:4];now=dt.datetime(2026,10,22,tzinfo=dt.timezone.utc)
        def event(q,days,outcome='independent'):return {'id':str(days),'question_id':q['id'],'variant':'main','mode':'parent','outcome':outcome,'hints':0,'student_saw_answer':False,'created_at':(now-dt.timedelta(days=days)).isoformat()}
        attempts=[event(qs[0],8),event(qs[1],4),event(qs[2],0)]
        find=lambda a:next(s for s in project(BANK,a,now)['skills'] if s['id']==qs[0]['skill_id'])
        self.assertEqual(find(attempts)['status'],'secure');self.assertEqual(find(attempts+[event(qs[3],0,'practice')])['status'],'needs_work')
    def test_ai_evidence_validation(self):
        q=BANK['questions'][0];data={'status':'attempted','met_points':['M1'],'evidence':{'M1':'down a gradient'},'gap_tags':['knowledge'],'score':99}
        self.assertEqual(validate(q,'Moves down a gradient.',data)['score'],1)
        with self.assertRaises(ValueError):validate(q,'Unrelated answer.',data)
if __name__=='__main__':unittest.main()
