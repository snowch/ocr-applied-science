const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const bank=JSON.parse(fs.readFileSync('content/exam-question-bank.json'));const context=vm.createContext({Date,URL,AbortSignal});
for(const name of ['learning','tutor','browser-store'])vm.runInContext(fs.readFileSync(`app/static/${name}.js`,'utf8'),context);
const {RevisionLearning:L,RevisionTutor:T}=context;const skill=bank.syllabus.skills[0];const forms=skill.question_ids.map(id=>bank.questions.find(q=>q.id===id));const now=Date.parse('2026-10-22T12:00:00Z');
function attempt(q,days,overrides={}){return {id:'test-'+days,question_id:q.id,variant:'main',mode:'parent',outcome:'independent',hints:0,student_saw_answer:false,created_at:new Date(now-days*86400000).toISOString(),...overrides}}
const get=attempts=>L.project(bank,attempts,now).skills.find(s=>s.id===skill.id);
test('secure evidence requires different items, three days, a week and application',()=>{
 assert.equal(get([]).status,'untested');assert.equal(get([attempt(forms[0],0)]).status,'improving');
 assert.equal(get([attempt(forms[0],8),attempt(forms[0],4),attempt(forms[0],0)]).status,'improving');
 assert.equal(get([attempt(forms[0],8),attempt(forms[2],4),attempt(forms[3],0)]).status,'improving');
 assert.equal(get([attempt(forms[0],8),attempt(forms[1],4),attempt(forms[2],0)]).status,'secure');
});
test('new difficulty reopens a secure gap and undo restores the prior evidence',()=>{
 const prior=[attempt(forms[0],8),attempt(forms[1],4),attempt(forms[2],1)];assert.equal(get(prior).status,'secure');
 const failed=attempt(forms[3],0,{outcome:'practice'});assert.equal(get([...prior,failed]).status,'needs_work');
 assert.equal(get([...prior,failed,attempt(forms[0],0)]).status,'improving');assert.equal(get(prior).status,'secure');
});
test('linked retest and its original form are one item, not two independent forms',()=>{
 const history=[attempt(forms[0],8),attempt(forms[0],4,{variant:'retest'}),attempt(forms[1],0)];assert.equal(get(history).independent_items,2);assert.equal(get(history).status,'improving');
});
test('scheduling includes both units, delays recent cramming and exposes reasons',()=>{
 const state=L.project(bank,[attempt(forms[0],0,{outcome:'practice'})],now);assert.equal(state.recommendations.length,bank.questions.length);assert.ok(state.recommendations.some(r=>r.unit==='F181'));assert.ok(state.recommendations[0].reason);assert.notEqual(state.recommendations[0].id,forms[0].id);
 const due=L.project(bank,[attempt(forms[0],2,{outcome:'practice'})],now);assert.equal(due.recommendations[0].skill_id,skill.id);assert.equal(due.skills.find(s=>s.id===skill.id).due,true);
});
test('AI totals are calculated from validated point IDs and exact answer evidence',()=>{
 const q=forms[0],answer='Facilitated diffusion moves down a gradient through proteins.';const data={status:'attempted',met_points:['M1'],evidence:{M1:'down a gradient through proteins'},gap_tags:['knowledge'],score:999,next_question:'What supplies energy for active transport?'};
 const review=T.validate(q,answer,data);assert.equal(review.score,1);assert.equal(review.max_marks,2);
 assert.throws(()=>T.validate(q,answer,{...data,met_points:['invented']}));assert.throws(()=>T.validate(q,answer,{...data,evidence:{M1:'an invented quote'}}));assert.throws(()=>T.validate(q,answer,{...data,status:'unattempted'}));assert.throws(()=>T.validate(q,answer,{...data,gap_tags:['mastered']}));
});
test('Mistral receives the current answer and rubric, without family history or keys in its prompt',async()=>{
 let request;const c=vm.createContext({Date,URL,AbortSignal,localStorage:{getItem:()=>JSON.stringify({key:'test-secret',model:'mistral-small-latest'})},sessionStorage:{getItem:()=>null},fetch:async function(url,options){assert.equal(this,c.globalThis||this);request={url,options};return {ok:true,json:async()=>({choices:[{message:{content:JSON.stringify({status:'attempted',met_points:['M1'],evidence:{M1:'down a gradient'},gap_tags:['knowledge'],next_question:'What about active transport?'})}}]})}}});vm.runInContext(fs.readFileSync('app/static/tutor.js','utf8'),c);
 const review=await c.RevisionTutor.grade(forms[0],'It moves down a gradient.');assert.equal(review.score,1);const body=JSON.parse(request.options.body);assert.equal(body.response_format.type,'json_object');assert.ok(body.messages[1].content.includes('down a gradient'));assert.ok(!request.options.body.includes('test-secret'));assert.ok(!request.options.body.includes('parent notes'));
});
test('AI progress review uses longitudinal skill evidence and rejects invented skill IDs',async()=>{
 let sent;let invented=false;const c=vm.createContext({Date,URL,AbortSignal,localStorage:{getItem:()=>JSON.stringify({key:'test-key',model:'mistral-small-latest'})},sessionStorage:{getItem:()=>null},fetch:async(url,options)=>{sent=JSON.parse(options.body);return {ok:true,json:async()=>({choices:[{message:{content:JSON.stringify({summary:'A later difficulty reopened this gap.',priorities:[{skill_id:invented?'not-a-skill':skill.id,reason:'Later answers needed help.',next_step:'Explain the mechanism, then attempt a different application.'}],next_session:'Repair this gap, then return tomorrow for a delayed check.'})}}]})}}});vm.runInContext(fs.readFileSync('app/static/tutor.js','utf8'),c);
 const skills=L.project(bank,[attempt(forms[0],2,{outcome:'practice'})],now).skills;const review=await c.RevisionTutor.coach(skills);assert.equal(review.priorities[0].skill_id,skill.id);const payload=JSON.parse(sent.messages[1].content);assert.equal(payload.skills[0].recent_evidence[0].outcome,'practice');assert.ok(!('answer' in payload.skills[0].recent_evidence[0]));invented=true;await assert.rejects(()=>c.RevisionTutor.coach(skills),/needs review/);
});
