import json
from pathlib import Path
import unittest

class ContentTests(unittest.TestCase):
    def test_pilot_has_distinct_questions_and_well_formed_rubrics(self):
        path=Path(__file__).resolve().parent.parent/'content'/'f181-question-bank.json'
        bank=json.loads(path.read_text());questions=bank['questions']
        self.assertEqual(len(questions),20)
        self.assertEqual(len({q['id'] for q in questions}),20)
        for q in questions:
            with self.subTest(question=q['id']):
                self.assertEqual(sum(p['marks'] for p in q['marking_points']),q['max_marks'])
                self.assertTrue(q['source']['url'].startswith('https://www.ocr.org.uk/'))
                self.assertTrue(q['model_answer'] and q['hints'] and q['follow_up'])
                self.assertNotEqual(q['question'],q['retest']['question'])
                ids={p['id'] for p in q['marking_points']}
                for trigger,implied in q.get('credit_dependencies',{}).items():
                    self.assertIn(trigger,ids);self.assertTrue(set(implied)<=ids)

if __name__=='__main__':unittest.main()
