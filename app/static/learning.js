/* Evidence-based scheduling; an AI opinion is not a verified grade. */
(function(global){
'use strict';
const DAY=86400000;
const GAP_TAGS=['knowledge','application','calculation','units','data','command_words','explanation'];
function project(bank,attempts,now=Date.now()){
 const lookup=new Map(bank.questions.map(q=>[q.id,q]));
 const groups=new Map();
 for(const q of bank.questions){const id=q.skill_id||q.id;if(!groups.has(id))groups.set(id,{id,title:q.skill||q.topic,unit:q.unit||'F181',area:q.area,topic:q.topic,question_ids:[]});groups.get(id).question_ids.push(q.id);}
 const skills=[...groups.values()].map(skill=>{
  const history=attempts.filter(a=>skill.question_ids.includes(a.question_id));
  const latest=history.at(-1);let status='untested',interval=0;
  // A later difficulty reopens the gap. Only evidence since that difficulty counts.
  let setback=-1;history.forEach((a,i)=>{if(a.outcome!=='independent')setback=i;});
  const independent=history.slice(setback+1).filter(a=>a.outcome==='independent'&&!a.hints&&!a.student_saw_answer);
  const eligible=independent.filter(a=>{const q=lookup.get(a.question_id);return (a.variant==='retest'?q.retest.demand:q.demand)!=='Integrated';});
  const items=new Set(eligible.map(a=>{const q=lookup.get(a.question_id);return a.variant==='retest'?(q.retest.item_key||q.id+'-R'):(q.item_key||q.id);}));
  const days=new Set(eligible.map(a=>new Date(a.created_at).toISOString().slice(0,10)));
  const span=eligible.length?Date.parse(eligible.at(-1).created_at)-Date.parse(eligible[0].created_at):0;
  const applied=eligible.some(a=>{const q=lookup.get(a.question_id);return a.variant==='retest'?q.retest.demand==='Application':q.demand==='Application';});
  if(latest){status=latest.outcome==='independent'?'improving':'needs_work';if(items.size>=3&&days.size>=3&&span>=7*DAY&&applied)status='secure';interval=status==='secure'?7:1;}
  const due=Boolean(latest&&now-Date.parse(latest.created_at)>=interval*DAY);
  const gaps=[...new Set(history.slice(-5).flatMap(a=>a.ai_review?.gap_tags||[]))];
  return {...skill,status,checks:history.length,independent_items:items.size,independent_days:days.size,last_checked:latest?.created_at||null,due,next_due:latest?new Date(Date.parse(latest.created_at)+interval*DAY).toISOString():null,gaps,history:history.slice(-8).map(a=>({id:a.id,date:a.created_at,outcome:a.outcome,mode:a.mode,assessment_origin:a.assessment_origin||'manual',ai_status:a.ai_review?.status||null,ai_score:a.ai_review?.score??null,ai_max_marks:a.ai_review?.max_marks??null})),latest_outcome:latest?.outcome||null};
 });
 // Work on a gap, then give time for consolidation; avoid immediate repeated cramming.
 const scored=bank.questions.map(q=>{
  const skill=skills.find(s=>s.id===(q.skill_id||q.id));
  const history=attempts.filter(a=>a.question_id===q.id);const latest=history.at(-1);
  const seenKeys=new Set(attempts.filter(a=>skill.question_ids.includes(a.question_id)).map(a=>{const p=lookup.get(a.question_id);return a.variant==='retest'?(p.retest.item_key||p.id+'-R'):(p.item_key||p.id);}));
  const mainSeen=seenKeys.has(q.item_key||q.id),retestSeen=seenKeys.has(q.retest.item_key||q.id+'-R');
  const variant=mainSeen&&!retestSeen?'retest':'main';
  const recent=latest&&now-Date.parse(latest.created_at)<20*60*1000;
  let score=skill.status==='needs_work'?(skill.due?0:4):skill.due?1:skill.status==='untested'?2:5;
  if(!mainSeen)score-=0.2;if(q.demand==='Integrated')score+=0.4;if(recent)score+=8;
  const unitSkills=skills.filter(s=>s.unit===q.unit);
  score+=0.1*unitSkills.filter(s=>s.checks).length/Math.max(1,unitSkills.length);
  return {id:q.id,unit:q.unit,skill_id:skill.id,variant,score,reason:skill.status==='needs_work'?'Repair a gap, then check it independently.':skill.due?'Check what has lasted after a delay.':skill.status==='untested'?'Diagnose an untested skill.':'Build breadth with another question.'};
 }).sort((a,b)=>a.score-b.score||a.id.localeCompare(b.id));
 return {skills,recommendations:scored,coverage:bank.syllabus?.areas||[],gap_tags:GAP_TAGS};
}
global.RevisionLearning={project,GAP_TAGS};
})(globalThis);
