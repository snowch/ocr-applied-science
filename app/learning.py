"""Local-server projection of evidence, matching the hosted browser policy."""
import datetime as dt
DAY=dt.timedelta(days=1)
def project(bank,attempts,now,teaching=None):
    teaching=teaching or []
    questions={q['id']:q for q in bank['questions']};groups={}
    def time(a):return dt.datetime.fromisoformat(a['created_at'].replace('Z','+00:00'))
    def item(a):
        q=questions[a['question_id']]
        return q['retest'].get('item_key',q['id']+'-R') if a['variant']=='retest' else q.get('item_key',q['id'])
    for q in questions.values():
        sid=q.get('skill_id',q['id'])
        groups.setdefault(sid,{'id':sid,'title':q.get('skill',q['topic']),'unit':q.get('unit','F181'),'area':q.get('area'),'topic':q['topic'],'question_ids':[]})['question_ids'].append(q['id'])
    skills=[]
    for skill in groups.values():
        history=[a for a in attempts if a['question_id'] in skill['question_ids']];latest=history[-1] if history else None
        setback=max((i for i,a in enumerate(history) if a['outcome']!='independent'),default=-1)
        independent=[a for a in history[setback+1:] if a['outcome']=='independent' and not a['hints'] and not a['student_saw_answer']]
        eligible=[a for a in independent if (questions[a['question_id']]['retest'] if a['variant']=='retest' else questions[a['question_id']]).get('demand')!='Integrated']
        items={item(a) for a in eligible};days={time(a).date() for a in eligible}
        span=time(eligible[-1])-time(eligible[0]) if eligible else dt.timedelta()
        applied=any((questions[a['question_id']]['retest'] if a['variant']=='retest' else questions[a['question_id']]).get('demand')=='Application' for a in eligible)
        status='untested' if not latest else 'improving' if latest['outcome']=='independent' else 'needs_work'
        if len(items)>=3 and len(days)>=3 and span>=7*DAY and applied:status='secure'
        knowledge_status=status
        records=[e for e in teaching if e['payload']['skill_id']==skill['id']];teaching_record=records[-1] if records else None;teaching_status=teaching_record['payload']['status'] if teaching_record else 'ready'
        if teaching_status=='not_taught':status='not_taught'
        interval=7 if status=='secure' else 1
        skills.append({**skill,'status':status,'knowledge_status':knowledge_status,'teaching_status':teaching_status,'teaching_record':{'date':teaching_record['recorded_at'],'mode':teaching_record['payload']['mode']} if teaching_record else None,'checks':len(history),'independent_items':len(items),'independent_days':len(days),'last_checked':latest['created_at'] if latest else None,'due':bool(teaching_status!='not_taught' and latest and now-time(latest)>=interval*DAY),'next_due':(time(latest)+interval*DAY).isoformat() if latest and teaching_status!='not_taught' else None,'gaps':list(dict.fromkeys(t for a in history[-5:] for t in a.get('ai_review',{}).get('gap_tags',[]))),'history':[{'id':a['id'],'date':a['created_at'],'outcome':a['outcome'],'mode':a['mode'],'assessment_origin':a.get('assessment_origin','manual'),'ai_status':a.get('ai_review',{}).get('status'),'ai_score':a.get('ai_review',{}).get('score'),'ai_max_marks':a.get('ai_review',{}).get('max_marks')} for a in history[-8:]],'latest_outcome':latest['outcome'] if latest else None})
    recommendations=[]
    for q in questions.values():
        skill=next(s for s in skills if s['id']==q.get('skill_id',q['id']))
        if skill['teaching_status']=='not_taught':continue
        history=[a for a in attempts if a['question_id']==q['id']]
        seen={item(a) for a in attempts if a['question_id'] in skill['question_ids']}
        main_seen=q.get('item_key',q['id']) in seen;retest_seen=q['retest'].get('item_key',q['id']+'-R') in seen
        variant='retest' if main_seen and not retest_seen else 'main'
        score=(0 if skill['due'] else 4) if skill['status']=='needs_work' else 1 if skill['due'] else 2 if skill['status']=='untested' else 5
        score-=0.2 if not main_seen else 0;score+=0.4 if q.get('demand')=='Integrated' else 0
        score+=8 if history and now-time(history[-1])<dt.timedelta(minutes=20) else 0
        unit_skills=[s for s in skills if s['unit']==q['unit']];score+=0.1*sum(s['checks']>0 for s in unit_skills)/max(1,len(unit_skills))
        recommendations.append({'id':q['id'],'unit':q['unit'],'skill_id':skill['id'],'variant':variant,'score':score,'reason':'Repair a gap, then check it independently.' if skill['status']=='needs_work' else 'Check what has lasted after a delay.' if skill['due'] else 'Diagnose an untested skill.' if skill['status']=='untested' else 'Build breadth with another question.'})
    return {'skills':skills,'recommendations':sorted(recommendations,key=lambda r:(r['score'],r['id'])),'coverage':bank['syllabus']['areas']}
