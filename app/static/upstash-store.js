/* Optional private, append-only shared storage. Never put credentials in deployed files. */
(function(global){
'use strict';
const CONFIG='f181:connection:v1';
const canonical=x=>JSON.stringify(x && typeof x==='object' ? (Array.isArray(x)?x.map(y=>JSON.parse(canonical(y))):Object.fromEntries(Object.keys(x).sort().map(k=>[k,JSON.parse(canonical(x[k]))]))) : x);
function configuration(input){
 const url=new URL(input.url);
 if(url.protocol!=='https:'||!url.hostname.endsWith('.upstash.io')||url.username||url.password||url.search||url.hash||url.pathname!=='/')throw Error('Use your HTTPS Upstash REST endpoint.');
 if(typeof input.token!=='string'||!input.token.trim()||input.token.length>4096)throw Error('Enter the restricted family token.');
 const key=input.key||'f181:events';
 if(!/^f181:[a-zA-Z0-9:_-]{1,100}$/.test(key))throw Error('Use a storage key starting with f181:.');
 return {url:url.origin,token:input.token.trim(),key,trial_expires:input.trial_expires||null};
}
class SharedRevisionStore{
 constructor(local,config,fetcher=global.fetch){this.local=local;this.config=configuration(config);this.fetcher=fetcher;this.error=null;this.synced=false;this.running=null;}
 events(){return this.local.events();}
 async command(command){
  const response=await this.fetcher(this.config.url,{method:'POST',headers:{Authorization:'Bearer '+this.config.token,'Content-Type':'application/json'},body:JSON.stringify(command),credentials:'omit',redirect:'error',signal:AbortSignal.timeout(12000)});
  if(!response.ok)throw Error('Shared storage could not be reached. Check the connection or retry.');
  const data=await response.json();if(data.error)throw Error('Shared storage rejected the request. Check the restricted token and storage key.');return data.result;
 }
 ackKey(id){return 'f181:ack:'+this.local.prefix+id;}
 pending(){return this.events().filter(e=>!this.local.storage.getItem(this.ackKey(e.event_id))).length;}
 validate(e,id){
  if(!e||e.schema_version!==1||e.event_id!==id||!/^([a-f0-9-]{36}|retract-[a-f0-9-]{36})$/i.test(id)||!Number.isFinite(Date.parse(e.recorded_at))||!e.payload||JSON.stringify(e).length>12000)throw Error('A shared observation is invalid.');
  const p=e.payload;
  if(e.type==='answer_observed'){
   if(!this.local.bank.questions.some(q=>q.id===p.question_id)||!['parent','self'].includes(p.mode)||!['independent','hint','practice'].includes(p.outcome)||!['main','retest'].includes(p.variant)||!Number.isInteger(p.hints)||p.hints<0||p.hints>2||typeof p.student_saw_answer!=='boolean'||typeof p.answer!=='string'||p.answer.length>2000||typeof p.note!=='string'||p.note.length>400)throw Error('A shared answer is invalid.');
  }else if(e.type!=='observation_retracted'||!/^[-a-f0-9]{36}$/i.test(p.target_event_id))throw Error('A shared observation is invalid.');
 }
 async performSync(){
  try{
   const entries=await this.command(['HGETALL',this.config.key]);
   if(!Array.isArray(entries)||entries.length%2)throw Error('Unexpected shared storage response.');
   const incoming=[];
   for(let i=0;i<entries.length;i+=2){const id=entries[i],e=JSON.parse(entries[i+1]);this.validate(e,id);const prior=this.local.storage.getItem(this.local.prefix+id);if(prior&&canonical(JSON.parse(prior))!==canonical(e))throw Error('Conflicting observation: export a backup before reconnecting.');incoming.push(e);}
   for(const e of incoming){this.local.storage.setItem(this.local.prefix+e.event_id,JSON.stringify(e));this.local.storage.setItem(this.ackKey(e.event_id),'1');}
   for(const e of this.events()){
    if(this.local.storage.getItem(this.ackKey(e.event_id)))continue;
    const result=await this.command(['HSETNX',this.config.key,e.event_id,JSON.stringify(e)]);
    if(result!==1){const prior=await this.command(['HGET',this.config.key,e.event_id]);if(!prior||canonical(JSON.parse(prior))!==canonical(e))throw Error('Conflicting observation: export a backup before reconnecting.');}
    this.local.storage.setItem(this.ackKey(e.event_id),'1');
   }
   this.error=null;this.synced=true;this.lastSync=new Date();
  }catch(e){this.error=e.message;this.synced=false;throw e;}
  finally{global.dispatchEvent?.(new Event('revision-sync'));}
 }
 sync(){if(!this.running)this.running=this.performSync().finally(()=>{this.running=null;});return this.running;}
 async request(path,body){
  if(path==='/api/state')await this.sync().catch(()=>{});
  const result=await this.local.request(path,body);
  if(body)await this.sync().catch(()=>{});
  return result;
 }
}
global.SharedRevisionStore=SharedRevisionStore;
global.revisionConnect=async function(input,remember){
 const config=configuration(input);await global.revisionStoreReady;
 const bank=global.revisionStore.local?.bank||global.revisionStore.bank;
 // Endpoint + key isolates families. Existing device-only records are not uploaded implicitly.
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(config.url+'|'+config.key));
 const scope=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
 const store=new SharedRevisionStore(new global.RevisionBrowserStore(bank,global.localStorage,'f181:shared:'+scope+':event:'),config);
 await store.sync();
 global.localStorage.removeItem(CONFIG);global.sessionStorage.removeItem(CONFIG);
 (remember?global.localStorage:global.sessionStorage).setItem(CONFIG,JSON.stringify(config));
 global.revisionStore=store;global.dispatchEvent(new Event('revision-sync'));return store;
};
global.revisionDisconnect=async function(){await global.revisionStoreReady;if(global.revisionStore.pending?.())throw Error('Sync pending observations before disconnecting.');const bank=global.revisionStore.local?.bank||global.revisionStore.bank;global.localStorage.removeItem(CONFIG);global.sessionStorage.removeItem(CONFIG);global.revisionStore=new global.RevisionBrowserStore(bank,global.localStorage);global.dispatchEvent(new Event('revision-sync'));};
if(global.REVISION_CONFIG?.storage==='browser'){
 const ready=global.revisionStoreReady;
 global.revisionStoreReady=ready.then(async()=>{
  let config;try{config=JSON.parse(global.localStorage.getItem(CONFIG)||global.sessionStorage.getItem(CONFIG)||'null');}catch{}
  if(config){
   const bank=global.revisionStore.bank;
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(config.url+'|'+config.key));
   const scope=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
   global.revisionStore=new SharedRevisionStore(new global.RevisionBrowserStore(bank,global.localStorage,'f181:shared:'+scope+':event:'),config);
   await global.revisionStore.sync().catch(()=>{});
  }
 });global.revisionStoreReady.catch(()=>{});
 const retry=()=>global.revisionStore?.sync?.().catch(()=>{});
 global.addEventListener('online',retry);global.document?.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')retry();});
 setInterval(()=>{if(global.document?.visibilityState==='visible')retry();},60000);
}
})(globalThis);
