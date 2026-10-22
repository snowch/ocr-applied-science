"""Build original exam practice from reviewable authored seeds, without API calls.

Four forms per skill are intentional: recall, application, misconception repair,
and a combined four-mark response. Retests link to another prepared form and are
not counted as extra questions. The bank is provisional, not OCR-approved.
"""
import json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent.parent
SOURCE='https://www.ocr.org.uk/Images/697579-specification-cambridge-advanced-national-in-applied-science.pdf'
AREAS={
'B1':('Cell structure and microscopy',33),'B2':('Bioenergetics',37),'B3':('Biological molecules',38),'B4':('Biodiversity and ecosystems',40),
'C1':('Atomic structure and the Periodic Table',42),'C2':('Quantitative chemistry',43),'C3':('Structure and bonding',45),'C4':('Reaction rates and enthalpy',47),
'P1':('Electricity',49),'P2':('Motion',52),'P3':('Medical physics',54),
'F181-1':('What scientists do',62),'F181-2':('Handling scientific data',64),'F181-3':('Scientific developments',66),'F181-4':('Communicating science',68)}
# Exact detailed teaching-content references. These map scope, not exhaustive depth.
REFS={
'B1':'1.1.1 1.1.2 1.1.3 1.2.1 1.2.2','B2':'2.1.1 2.1.2 2.2.1 2.2.2','B3':'3.1.1 3.1.2 3.1.3 3.1.4','B4':'4.1.1 4.2.1 4.2.2',
'C1':'1.1.1 1.2','C2':'2.1.1 2.1.2 2.1.3 2.1.4 2.1.5 2.1.6','C3':'3.1.1 3.1.2 3.2.1 3.3.1','C4':'4.1.1 4.1.2 4.2.1 4.2.2',
'P1':'1.1.1 1.1.2 1.1.3 1.1.4 1.1.5 1.1.6','P2':'2.1.1 2.1.2 2.1.3 2.1.4 2.1.5 2.1.6','P3':'3.1.1 3.1.2 3.1.3 3.1.4 3.1.5 3.2.1 3.2.2 3.2.3 3.2.4',
'F181-1':'1.1.1 1.2.1 1.2.2 1.3.1 1.3.2 1.3.3 1.4','F181-2':'2.1 2.2 2.3.1 2.3.2 2.4.1','F181-3':'3.1.1 3.1.2 3.2.1 3.2.2 3.3.1 3.3.2','F181-4':'4.1.1 4.1.2 4.2 4.3 4.4.1 4.4.2'}
rows=[line.split('|') for line in (ROOT/'content/source/exam-skills.txt').read_text().splitlines() if line and not line.startswith('#')]
corrections=(ROOT/'content/source/misconception-corrections.txt').read_text().splitlines()
assert len(rows)==len(corrections)
questions=[];skills=[]
def points(items):return [{'id':f'M{i+1}','marks':1,'criterion':s} for i,s in enumerate(items)]
for index,(row,correction) in enumerate(zip(rows,corrections),1):
 area,ref,title,rq,rp,aq,ap,wrong=row;unit='F181' if area.startswith('F181') else 'F180';sid=f'{unit}-S{index:03}'
 recall=rp.split('~');application=ap.split('~');correct=correction.split('~');assert len(recall)==len(application)==len(correct)==2
 forms=[(rq,recall,'Recall'),(aq,application,'Application'),(f'A student claims: “{wrong}” Explain precisely what is wrong and give the correct scientific account.',correct,'Misconception'),(rq+' Then apply your explanation: '+aq,recall+application,'Integrated')]
 ids=[f'{unit}-Q{index:03}{letter}' for letter in 'ABCD']
 skills.append({'id':sid,'unit':unit,'area':area,'title':title,'reference':ref,'question_ids':ids})
 for j,(text,rubric,demand) in enumerate(forms):
  other=[1,2,0,1][j];rt=forms[other]
  questions.append({'id':ids[j],'unit':unit,'area':area,'skill_id':sid,'skill':title,'topic':unit+' · '+AREAS[area][0],
    'specification_sections':[area+':'+ref], 'source':{'url':SOURCE,'version':'7.0 June 2026','pdf_page':AREAS[area][1],'supports':'Topic-area starting page; generated original question and provisional rubric.'},
    'demand':demand,'question':text,'item_key':ids[j],'max_marks':len(rubric),'marking_points':points(rubric),'model_answer':' '.join(rubric),
    'marking_rules':['Accept scientifically equivalent wording. Award each distinct point once.','Withhold a point if directly contradicted. Do not reward unsupported claims.','Numerical method and result are separate points where listed. Equivalent consistent units are acceptable.','Provisional point-based practice rubric; not an official OCR marking or levels-of-response scheme.'],
    'common_misconception':wrong,'hints':[f'Identify the key ideas in {title.lower()}. State the relevant relationship before applying it.','One starting point: '+rubric[0]],
    'follow_up':rt[0], 'repair':{'explanation':' '.join(correct),'worked_example':aq+'\n'+' '.join(application),'check':rq},
    'retest':{'question':rt[0],'item_key':ids[other],'demand':rt[2],'max_marks':len(rt[1]),'marking_points':points(rt[1])},
    'review_status':'generated_provisional','estimated_seconds':90 if len(rubric)==2 else 180})
pilot=json.loads((ROOT/'content/source/f181-pilot.json').read_text())
# Keep stable IDs so existing family records remain readable after the upgrade.
pilot_skill_titles=['Theories and laws','Theories and laws','Scientific method','Scientific method','Scientific method','Iterative science','Scientific method','Hypotheses and reasoning','Peer review and expert communication','Peer review and expert communication','Peer review and expert communication','International research projects','Scientific collaboration','Types of data','Types of data','Types of data','Quantitative interpretation','Quantitative interpretation','Correlation and conclusions','Sampling and bias']
for q,title in zip(pilot['questions'],pilot_skill_titles):
 linked=next(s for s in skills if s['title']==title)
 linked['question_ids'].append(q['id'])
 q.update(unit='F181',area='F181-'+q['specification_sections'][0][0],skill_id=linked['id'],skill=title,item_key=q['id'],review_status='generated_provisional',estimated_seconds=90)
 q['retest']['item_key']=q['id']+'-R';q['topic']='F181 · '+q['topic'];questions.append(q)
coverage={'specification':{'url':SOURCE,'version':'7.0 June 2026'},'units':[{'id':'F180','title':'Fundamentals of science','minutes':90,'marks':70},{'id':'F181','title':'Science in society','minutes':75,'marks':50}],
'areas':[{'id':area,'unit':'F181' if area.startswith('F181') else 'F180','title':title,'pdf_page':page,'references':[{'id':ref,'practice_items':sum(q['area']==area and area+':'+ref in q['specification_sections'] for q in questions)} for ref in REFS[area].split()]} for area,(title,page) in AREAS.items()],
'skills':skills,'limits':['Every detailed teaching-content reference has starter practice, but this does not establish exhaustive coverage of every breadth-and-depth bullet.','Diagram drawing, photographic interpretation, full papers and official levels-of-response marking need additional material.','No exam-series pre-release has been selected. F181 scenarios are general practice, not predictions of the examination.','Four forms per skill deliberately share concepts; integrated forms reuse recall and application components. Retests reuse linked forms and are not extra unique questions.','All generated scientific content and rubrics await independent subject-teacher review.']}
bank={'title':'F180 and F181 exam practice','qualification':pilot['qualification'],'version':'1.0','created':'2026-10-22','authorship':'Original practice authored in this ChatGPT session; deterministic packaging, no bulk model API calls.','status':'Generated provisional practice; independent teacher review pending. Not OCR exam questions or grade predictions.','coverage':coverage['limits'],'session_rules':pilot['session_rules'],'syllabus':coverage,'questions':questions}
(ROOT/'content/exam-question-bank.json').write_text(json.dumps(bank,indent=2,ensure_ascii=False)+'\n')
(ROOT/'content/exam-coverage.json').write_text(json.dumps(coverage,indent=2,ensure_ascii=False)+'\n')
counts=Counter(q['unit'] for q in questions)
report=f"# Exam practice coverage\n\n{len(questions)} main question entries: {dict(counts)}. {len(skills)} new skills, each with four related forms, plus 20 preserved pilot questions. Linked retests are not counted as extra questions.\n\n"
report+='| Unit / area | Starter items | Detailed references with practice |\n|---|---:|---:|\n'
for a in coverage['areas']:report+=f"| {a['unit']} {a['id']} — {a['title']} | {sum(q['area']==a['id'] for q in questions)} | {sum(r['practice_items']>0 for r in a['references'])}/{len(a['references'])} |\n"
report+='\n'+'\n'.join('- '+x for x in coverage['limits'])+'\n'
(ROOT/'docs/exam-coverage.md').write_text(report)
print(f'Built {len(questions)} entries across {len(skills)} skills: {dict(counts)}')
if __name__=='__main__':assert all(r['practice_items'] for a in coverage['areas'] for r in a['references'])
