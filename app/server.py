"""Local shared-data prototype. Run: python -m app.server (loopback only).

This has no hosted login integration and deliberately cannot bind publicly.
All browser sessions connected to this instance use the same practice learner.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import datetime as dt
import json
import uuid
from urllib.parse import urlparse, parse_qs
from .event_store import EventStore

ROOT=Path(__file__).parent
BANK=json.loads((ROOT.parent/'content'/'f181-question-bank.json').read_text())
QUESTIONS={q['id']:q for q in BANK['questions']}
UTC=dt.timezone.utc
STORE=EventStore(ROOT.parent/'data'/'events')

def initialise():
    STORE.initialise()

def read_attempts():
    events=STORE.all()
    withdrawn={event['payload']['target_event_id'] for event in events if event['type']=='observation_retracted'}
    return [{**event['payload'],'id':event['event_id'],'created_at':event['recorded_at']}
            for event in events if event['type']=='answer_observed' and event['event_id'] not in withdrawn]

def record(body):
    if not isinstance(body,dict): raise ValueError('Invalid request')
    try: identifier=str(uuid.UUID(body.get('id','')))
    except (ValueError,AttributeError,TypeError): raise ValueError('Invalid save identifier')
    qid=body.get('question_id')
    if qid not in QUESTIONS: raise ValueError('Unknown question')
    variant=body.get('variant','main'); mode=body.get('mode'); outcome=body.get('outcome')
    if variant not in ('main','retest') or mode not in ('parent','self') or outcome not in ('independent','hint','practice'):
        raise ValueError('Invalid answer record')
    hints=body.get('hints',0)
    if type(hints) is not int or not 0<=hints<=2: raise ValueError('Invalid hint count')
    saw=body.get('student_saw_answer',False)
    if type(saw) is not bool: raise ValueError('Invalid answer visibility')
    answer=body.get('answer','');note=body.get('note','')
    if not isinstance(answer,str) or len(answer)>2000 or not isinstance(note,str) or len(note)>400:
        raise ValueError('Answer or note is too long')
    if outcome=='independent' and (hints or saw): outcome='hint'
    payload={'student_id':'practice-learner','question_id':qid,'question_version':BANK['version'],
             'variant':variant,'mode':mode,'outcome':outcome,'hints':hints,
             'student_saw_answer':saw,'answer':answer.strip(),'note':note.strip()}
    event=STORE.append(identifier,'answer_observed',payload)
    return {**event['payload'],'id':event['event_id'],'created_at':event['recorded_at']}

def retract(identifier):
    identifier=str(uuid.UUID(identifier))
    target=STORE.get(identifier)
    if not target or target['type']!='answer_observed':raise ValueError('Unknown observation')
    event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'local-prototype:retract:'+identifier))
    STORE.append(event_id,'observation_retracted',{'target_event_id':identifier,'student_id':'practice-learner'})

def state():
    attempts=read_attempts();now=dt.datetime.now(UTC)
    result=[];topics={}
    for qid,q in QUESTIONS.items():
        history=[a for a in attempts if a['question_id']==qid]
        latest=history[-1] if history else None
        status=latest['outcome'] if latest else 'new'
        retained=False
        if latest and latest['variant']=='retest' and latest['outcome']=='independent':
            latest_time=dt.datetime.fromisoformat(latest['created_at'])
            retained=any(a['outcome']=='independent' and latest_time-dt.datetime.fromisoformat(a['created_at'])>=dt.timedelta(days=1) for a in history[:-1])
        due=bool(latest and now-dt.datetime.fromisoformat(latest['created_at'])>=dt.timedelta(days=1))
        entry={'id':qid,'topic':q['topic'],'status':status,'later_retest':retained,'due':due,
               'next_variant':'retest' if due else 'main','attempts':len(history),'latest':latest}
        result.append(entry)
        topic=topics.setdefault(q['topic'],{'name':q['topic'],'total':0,'seen':0,'independent':0,'needs_practice':0,'retested':0})
        topic['total']+=1
        topic['seen']+=int(bool(history))
        topic['independent']+=int(status=='independent')
        topic['needs_practice']+=int(status in ('hint','practice'))
        topic['retested']+=int(retained)
    ordered=sorted(result,key=lambda q:(0 if q['status'] in ('hint','practice') else 1 if q['due'] else 2 if q['status']=='new' else 3,q['id']))
    return {'questions':result,'topics':list(topics.values()),'recent':list(reversed(attempts))[:20],
            'suggested':ordered[0] if ordered else None,'total_attempts':len(attempts),'server_time':now.isoformat()}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def local_host(self):
        return self.headers.get('Host','').split(':')[0] in ('127.0.0.1','localhost')
    def send_json(self,status,value):
        data=json.dumps(value).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if not self.local_host():return self.send_json(403,{'error':'Local prototype only'})
        url=urlparse(self.path)
        if url.path=='/api/state':
            try:return self.send_json(200,state())
            except (OSError,ValueError,KeyError,TypeError):return self.send_json(503,{'error':'Progress could not be read. Please retry or check the event folder.'})
        if url.path=='/api/question':
            query=parse_qs(url.query);qid=query.get('id',[''])[0];variant=query.get('variant',['main'])[0]
            if qid not in QUESTIONS or variant not in ('main','retest'):return self.send_json(404,{'error':'Question not found'})
            q=QUESTIONS[qid];item=q if variant=='main' else q['retest']
            return self.send_json(200,{'id':qid,'variant':variant,'topic':q['topic'],'question':item['question'],'source':q['source'],
                'hints':q['hints'] if variant=='main' else ['Think back to the concept you practised. Try explaining it in your own words.'],
                'marking_points':item['marking_points'],'model_answer':q['model_answer'] if variant=='main' else ' '.join(p['criterion'] for p in item['marking_points'])})
        if url.path in ('/','/app.js','/style.css','/config.js','/browser-store.js'):
            name='index.html' if url.path=='/' else url.path[1:]
            data=(ROOT/'static'/name).read_bytes();self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8' if url.path=='/' else 'text/css; charset=utf-8' if name.endswith('.css') else 'text/javascript; charset=utf-8')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        return self.send_json(404,{'error':'Not found'})
    def do_POST(self):
        if not self.local_host():return self.send_json(403,{'error':'Local prototype only'})
        # Local requests must be same-origin. No broad CORS or public listener.
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host',''):return self.send_json(403,{'error':'Origin not allowed'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=12000:raise ValueError('Invalid request size')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Expected JSON')
            body=json.loads(self.rfile.read(length))
            if self.path=='/api/attempts':return self.send_json(200,record(body))
            if self.path=='/api/undo':
                identifier=str(uuid.UUID(body.get('id','')))
                retract(identifier)
                return self.send_json(200,{'ok':True})
            return self.send_json(404,{'error':'Not found'})
        except (ValueError,TypeError,AttributeError):return self.send_json(400,{'error':'Could not save this answer. Check the details and try again.'})
        except OSError:return self.send_json(503,{'error':'Progress could not be saved. Please retry.'})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    initialise();print('Local prototype: http://127.0.0.1:'+str(args.port),flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
