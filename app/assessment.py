"""Validate suggested AI rubric credit, never trust a model-provided total."""
def validate(question,answer,data):
    normalise=lambda s:' '.join(s.lower().split())
    allowed={p['id']:p for p in question['marking_points']}
    tags={'knowledge','application','calculation','units','data','command_words','explanation'}
    if not isinstance(data,dict) or data.get('status') not in ('attempted','unattempted','needs_clarification'):raise ValueError('Invalid AI review')
    ids=data.get('met_points');evidence=data.get('evidence');gaps=data.get('gap_tags')
    if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or len(ids)!=len(set(ids)) or not isinstance(evidence,dict) or not isinstance(gaps,list) or any(not isinstance(t,str) or t not in tags for t in gaps):raise ValueError('Invalid AI review')
    quotes={}
    for i in ids:
        quote=evidence.get(i)
        if i not in allowed or not isinstance(quote,str) or not quote.strip() or normalise(quote) not in normalise(answer):raise ValueError('Unsupported AI review')
        quotes[i]=quote
    if data['status']!='attempted' and ids:raise ValueError('Invalid AI credit')
    credit=set(ids)
    for trigger,implied in question.get('credit_dependencies',{}).items():
        if trigger in credit:credit.update(i for i in implied if i in allowed)
    return {'source':'mistral','status':data['status'],'met_points':ids,'evidence':quotes,'score':sum(allowed[i]['marks'] for i in credit) if data['status']=='attempted' else None,'max_marks':question.get('max_marks',sum(p['marks'] for p in allowed.values())),'gap_tags':list(dict.fromkeys(gaps)),'next_question':data.get('next_question','')[:500] if isinstance(data.get('next_question',''),str) else '', 'model':data.get('model','mistral-small-latest')[:100] if isinstance(data.get('model',''),str) else 'mistral-small-latest'}

def outcome(review,hints,saw):
    if not review or review['status']!='attempted':raise ValueError('Clarify the answer before saving an AI result')
    return 'practice' if review['score']<review['max_marks'] else 'hint' if hints or saw else 'independent'
