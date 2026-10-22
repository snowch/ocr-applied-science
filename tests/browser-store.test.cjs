const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const bank = JSON.parse(fs.readFileSync(path.join(root, 'content/f181-question-bank.json')));
class MemoryStorage {
  constructor(){this.map=new Map()}
  get length(){return this.map.size}
  key(i){return [...this.map.keys()][i]??null}
  getItem(key){return this.map.get(key)??null}
  setItem(key,value){this.map.set(key,String(value))}
}
function setup(storage=new MemoryStorage()) {
  const context=vm.createContext({URL,Date,console,REVISION_CONFIG:{storage:'server'}});
  vm.runInContext(fs.readFileSync(path.join(root,'app/static/browser-store.js'),'utf8'),context);
  return {store:new context.RevisionBrowserStore(bank,storage),storage};
}
function answer(extra={}) {return {id:'bfb456b0-2cb7-479f-b03c-86f0a8c0b1d2',question_id:'F181-P01',variant:'main',mode:'parent',outcome:'independent',hints:0,student_saw_answer:false,answer:'Explains why; describes what.',note:'Clear explanation',...extra}}
test('static question path works under the project site without a Python API',async()=>{
  const {store}=setup();const q=await store.request('/api/question?id=F181-P01&variant=retest');
  assert.equal(q.variant,'retest');assert.ok(q.question);assert.equal(q.marking_points.length,2);
});
test('records persist across store instances and identical retries do not duplicate',async()=>{
  const {store,storage}=setup();const initial=await store.request('/api/attempts',answer());
  const retry=await setup(storage).store.request('/api/attempts',answer());
  assert.equal(initial.created_at,retry.created_at);assert.equal(storage.length,1);
  assert.equal(setup(storage).store.state().total_attempts,1);
  await assert.rejects(()=>store.request('/api/attempts',answer({note:'different'})));
});
test('undo appends a retraction and preserves original event bytes',async()=>{
  const {store,storage}=setup();await store.request('/api/attempts',answer());
  const key=storage.key(0),before=storage.getItem(key);
  await store.request('/api/undo',{id:answer().id});await store.request('/api/undo',{id:answer().id});
  assert.equal(storage.getItem(key),before);assert.equal(storage.length,2);assert.equal(store.state().total_attempts,0);
});
test('hints cannot be recorded as independent and one answer is not retention',async()=>{
  const {store}=setup();const record=await store.request('/api/attempts',answer({hints:1}));
  assert.equal(record.outcome,'hint');assert.equal(store.state().questions[0].later_retest,false);
});
test('a later-day retest adds evidence and a subsequent difficulty takes precedence',async()=>{
  const {store,storage}=setup();const body=answer();
  await store.request('/api/attempts',body);
  // Fixture setup only: simulate an older event before testing the projection.
  const key=storage.key(0),event=JSON.parse(storage.getItem(key));
  event.recorded_at=new Date(Date.now()-2*24*60*60*1000).toISOString();storage.setItem(key,JSON.stringify(event));
  await store.request('/api/attempts',answer({id:'fbaaa860-666f-42f1-8da8-e157e7e055bb',variant:'retest'}));
  assert.equal(store.state().questions[0].later_retest,true);
  await store.request('/api/attempts',answer({id:'fffff860-666f-42f1-8da8-e157e7e055bb',outcome:'practice'}));
  assert.equal(store.state().questions[0].status,'practice');assert.equal(store.state().questions[0].later_retest,false);
});
test('bad records and unavailable storage fail rather than reporting a save',async()=>{
  const {store}=setup();await assert.rejects(()=>store.request('/api/attempts',answer({question_id:'unknown'})));
  const unavailable={get length(){return 0},getItem(){return null},setItem(){throw Error('Quota exceeded')}};
  await assert.rejects(()=>setup(unavailable).store.request('/api/attempts',answer()));
});
