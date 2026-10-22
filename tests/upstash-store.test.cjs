const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');const {randomUUID}=require('node:crypto');
const bank=JSON.parse(fs.readFileSync('content/exam-question-bank.json'));
class Memory{constructor(){this.m=new Map()}get length(){return this.m.size}key(i){return [...this.m.keys()][i]}getItem(k){return this.m.get(k)||null}setItem(k,v){this.m.set(k,String(v))}}
function client(fetcher,config={url:'https://example.upstash.io',token:'restricted',key:'f181:test:events'}){const c=vm.createContext({URL,Date,Event,AbortSignal,console,setInterval});for(const f of ['learning','tutor','browser-store','upstash-store'])vm.runInContext(fs.readFileSync(`app/static/${f}.js`,'utf8'),c);return new c.SharedRevisionStore(new c.RevisionBrowserStore(bank,new Memory(),'test:event:'),config,fetcher)}
function answer(){return {id:randomUUID(),question_id:bank.questions[0].id,variant:'main',mode:'parent',outcome:'independent',hints:0,student_saw_answer:false,answer:'Test answer',note:'Synthetic sync test'}}
test('two devices exchange observations, retries, retractions and offline saves',async()=>{
 const remote=new Map();let offline=false;
 const fetcher=async(url,options)=>{if(offline)throw Error('Offline');const [cmd,key,id,value]=JSON.parse(options.body);let result;if(cmd==='HGETALL')result=[...remote].flat();else if(cmd==='HSETNX'){result=remote.has(id)?0:1;if(result)remote.set(id,value);}else result=remote.get(id)||null;return {ok:true,json:async()=>({result})}};
 const a=client(fetcher),b=client(fetcher),record=answer();await a.request('/api/attempts',record);await b.sync();assert.equal(b.local.state().total_attempts,1);await a.request('/api/attempts',record);assert.equal(remote.size,1);
 const original=remote.get(record.id);await b.request('/api/undo',{id:record.id});await a.sync();assert.equal(a.local.state().total_attempts,0);assert.equal(remote.get(record.id),original);
 offline=true;await a.request('/api/attempts',answer());assert.equal(a.pending(),1);assert.ok(a.error);offline=false;await a.sync();assert.equal(a.pending(),0);await b.sync();assert.equal(b.local.state().total_attempts,1);
});
test('remote conflicts cannot overwrite local observations',async()=>{let entries=[];const c=client(async()=>({ok:true,json:async()=>({result:entries})}));await c.local.request('/api/attempts',answer());const e=c.events()[0];entries=[e.event_id,JSON.stringify({...e,payload:{...e.payload,note:'changed'}})];await assert.rejects(()=>c.sync(),/Conflicting/);assert.notEqual(c.events()[0].payload.note,'changed');});
test('unsafe endpoints are rejected',()=>{assert.throws(()=>client(()=>{},{url:'http://example.upstash.io',token:'x'}));assert.throws(()=>client(()=>{},{url:'https://evil.test',token:'x'}));});
test('live trial exchanges observations using only the restricted test token',{skip:!process.env.F181_LIVE_CONNECTION},async()=>{const config=JSON.parse(fs.readFileSync(process.env.F181_LIVE_CONNECTION));const a=client(fetch,config),b=client(fetch,config),record=answer();const q=bank.questions[0];record.answer=q.marking_points[0].criterion;record.elapsed_seconds=17;record.assessment_origin='ai';record.ai_review={status:'attempted',met_points:[q.marking_points[0].id],evidence:{[q.marking_points[0].id]:record.answer},gap_tags:['knowledge'],model:'synthetic-fixture'};await a.request('/api/attempts',record);assert.equal(a.error,null);await b.sync();const shared=b.events().find(e=>e.event_id===record.id);assert.ok(shared);assert.equal(shared.payload.ai_review.score,1);assert.equal(shared.payload.elapsed_seconds,17);assert.equal(shared.payload.assessment_origin,'ai');assert.equal(shared.payload.outcome,'practice');await b.request('/api/undo',{id:record.id});await a.sync();assert.ok(a.events().some(e=>e.event_id==='retract-'+record.id));await a.request('/api/teaching-status',{id:randomUUID(),skill_id:q.skill_id,status:'not_taught',mode:'self'});await b.sync();assert.equal((await b.request('/api/state')).skills.find(s=>s.id===q.skill_id).status,'not_taught');await b.request('/api/teaching-status',{id:randomUUID(),skill_id:q.skill_id,status:'ready',mode:'parent'});await a.sync();assert.notEqual((await a.request('/api/state')).skills.find(s=>s.id===q.skill_id).status,'not_taught');});

test('native browser fetch keeps its Window receiver',async()=>{
 const c=vm.createContext({URL,Date,Event,AbortSignal,console,setInterval});
 vm.runInContext(`globalThis.fetch=async function(){if(this!==globalThis)throw Error('fetch requires Window');return {ok:true,json:async()=>({result:[]})}}`,c);
 for(const f of ['learning','tutor','browser-store','upstash-store'])vm.runInContext(fs.readFileSync(`app/static/${f}.js`,'utf8'),c);
 const store=new c.SharedRevisionStore(new c.RevisionBrowserStore(bank,new Memory()),{url:'https://example.upstash.io',token:'restricted',key:'f181:test:events'});
 await store.sync();assert.equal(store.synced,true);assert.equal(store.error,null);
});

test('teaching status syncs across devices without adding or removing answer evidence',async()=>{
 const remote=new Map();const fetcher=async(url,options)=>{const [cmd,key,id,value]=JSON.parse(options.body);let result;if(cmd==='HGETALL')result=[...remote].flat();else if(cmd==='HSETNX'){result=remote.has(id)?0:1;if(result)remote.set(id,value)}else result=remote.get(id)||null;return {ok:true,json:async()=>({result})}};
 const a=client(fetcher),b=client(fetcher),skill=bank.questions[0].skill_id;await a.request('/api/teaching-status',{id:randomUUID(),skill_id:skill,status:'not_taught',mode:'self'});await b.sync();let state=await b.request('/api/state');assert.equal(state.total_attempts,0);assert.equal(state.skills.find(s=>s.id===skill).status,'not_taught');assert.ok(!state.recommendations.some(q=>q.skill_id===skill));
 await b.request('/api/teaching-status',{id:randomUUID(),skill_id:skill,status:'ready',mode:'parent'});await a.sync();state=await a.request('/api/state');assert.equal(state.total_attempts,0);assert.equal(state.skills.find(s=>s.id===skill).status,'untested');assert.equal(remote.size,2);
});

test('existing device history can be explicitly shared, retained and recovered after remote loss',async()=>{
 const remote=new Map();const fetcher=async(url,options)=>{const [cmd,key,id,value]=JSON.parse(options.body);let result;if(cmd==='HGETALL')result=[...remote].flat();else if(cmd==='HSETNX'){result=remote.has(id)?0:1;if(result)remote.set(id,value)}else result=remote.get(id)||null;return {ok:true,json:async()=>({result})}};
 const a=client(fetcher),b=client(fetcher);
 // Default device-only namespace, distinct from the active family namespace.
 const device=new a.local.constructor(bank,a.local.storage);
 const record=answer();await device.request('/api/attempts',record);
 await device.request('/api/teaching-status',{id:randomUUID(),skill_id:bank.questions[1].skill_id,status:'not_taught',mode:'self'});
 await a.sync();assert.equal(remote.size,0);assert.equal(a.unsharedDeviceEvents().length,2);
 const originals=JSON.stringify(device.events());await a.shareDeviceProgress();await b.sync();
 assert.equal(b.local.state().total_attempts,1);assert.equal(remote.size,2);assert.equal(JSON.stringify(device.events()),originals);assert.equal(a.unsharedDeviceEvents().length,0);
 await a.shareDeviceProgress();assert.equal(remote.size,2);
 remote.clear();await a.sync();assert.equal(remote.size,2);assert.equal(a.pending(),0);
 // Same ID with different content must never silently replace history.
 const event=device.events().find(e=>e.type==='answer_observed');
 device.storage.setItem(device.prefix+event.event_id,JSON.stringify({...event,payload:{...event.payload,note:'conflict'}}));
 await assert.rejects(()=>a.shareDeviceProgress(),/Conflicting/);assert.equal(remote.size,2);assert.equal(a.events().find(e=>e.event_id===event.event_id).payload.note,event.payload.note);
});
