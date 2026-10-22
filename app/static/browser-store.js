/* GitHub Pages preview: append-only records in this browser, never in Git. */
(function (global) {
  'use strict';
  const PREFIX = 'f181-preview:event:';
  const DAY = 24 * 60 * 60 * 1000;
  const stable = value => JSON.stringify(value && typeof value === 'object' ? (Array.isArray(value) ? value.map(v => JSON.parse(stable(v))) : Object.fromEntries(Object.keys(value).sort().map(k => [k, JSON.parse(stable(value[k]))]))) : value);
  class RevisionBrowserStore {
    constructor(bank, storage, prefix = PREFIX) { this.bank = bank; this.storage = storage; this.prefix = prefix; }
    events() {
      const events = [];
      for (let i = 0; i < this.storage.length; i++) {
        const key = this.storage.key(i);
        if (!key.startsWith(this.prefix)) continue;
        const event = JSON.parse(this.storage.getItem(key));
        if (event.schema_version !== 1 || !['answer_observed', 'observation_retracted'].includes(event.type)) {
          throw Error('A saved record could not be read. Back up your records before making changes.');
        }
        events.push(event);
      }
      return events.sort((a, b) => a.recorded_at.localeCompare(b.recorded_at) || a.event_id.localeCompare(b.event_id));
    }
    append(id, type, payload) {
      const key = this.prefix + id;
      const prior = this.storage.getItem(key);
      if (prior) {
        const event = JSON.parse(prior);
        if (event.type !== type || stable(event.payload) !== stable(payload)) throw Error('This save identifier has already been used.');
        return event;
      }
      const event = { schema_version: 1, event_id: id, type, recorded_at: new Date().toISOString(), payload };
      this.storage.setItem(key, JSON.stringify(event));
      return event;
    }
    attempts() {
      const events = this.events();
      const withdrawn = new Set(events.filter(e => e.type === 'observation_retracted').map(e => e.payload.target_event_id));
      return events.filter(e => e.type === 'answer_observed' && !withdrawn.has(e.event_id))
        .map(e => ({ ...e.payload, id: e.event_id, created_at: e.recorded_at }));
    }
    state() {
      const attempts = this.attempts(), topics = new Map(), now = Date.now();
      const questions = this.bank.questions.map(q => {
        const history = attempts.filter(a => a.question_id === q.id), latest = history.at(-1);
        const status = latest?.outcome || 'new';
        const retained = Boolean(latest && latest.variant === 'retest' && status === 'independent' &&
          history.slice(0, -1).some(a => a.outcome === 'independent' && Date.parse(latest.created_at) - Date.parse(a.created_at) >= DAY));
        const due = Boolean(latest && now - Date.parse(latest.created_at) >= DAY);
        if (!topics.has(q.topic)) topics.set(q.topic, { name: q.topic, total: 0, seen: 0, independent: 0, needs_practice: 0, retested: 0 });
        const topic = topics.get(q.topic);
        topic.total++; topic.seen += history.length > 0; topic.independent += status === 'independent';
        topic.needs_practice += ['hint', 'practice'].includes(status); topic.retested += retained;
        return { id: q.id, unit: q.unit || 'F181', skill_id: q.skill_id || q.id, skill: q.skill || q.topic, demand: q.demand, topic: q.topic, status, later_retest: retained, due, next_variant: due ? 'retest' : 'main', attempts: history.length, latest: latest || null };
      });
      const rank = q => ['hint', 'practice'].includes(q.status) ? 0 : q.due ? 1 : q.status === 'new' ? 2 : 3;
      const ordered = [...questions].sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id));
      const learning = global.RevisionLearning?.project(this.bank, attempts) || {};
      return { ...learning, questions, topics: [...topics.values()], recent: [...attempts].reverse().slice(0, 20), suggested: ordered[0], total_attempts: attempts.length, server_time: new Date().toISOString() };
    }
    async request(path, body) {
      const url = new URL(path, 'https://preview.invalid');
      if (url.pathname === '/api/state') return this.state();
      if (url.pathname === '/api/question') {
        const q = this.bank.questions.find(q => q.id === url.searchParams.get('id'));
        const variant = url.searchParams.get('variant') || 'main';
        if (!q || !['main', 'retest'].includes(variant)) throw Error('Question not found.');
        const item = variant === 'main' ? q : q.retest;
        return { ...q, ...item, id: q.id, item_key: item.item_key || (variant === 'main' ? q.id : q.id + '-R'), variant, unit: q.unit || 'F181', topic: q.topic, question: item.question, source: q.source,
          hints: variant === 'main' ? q.hints : ['Think back to the concept you practised. Try explaining it in your own words.'],
          marking_points: item.marking_points, model_answer: variant === 'main' ? q.model_answer : item.marking_points.map(p => p.criterion).join(' ') };
      }
      if (url.pathname === '/api/attempts') {
        if (!body || !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(body.id) ||
            !this.bank.questions.some(q => q.id === body.question_id) || !['main', 'retest'].includes(body.variant) ||
            !['parent', 'self'].includes(body.mode) || !['independent', 'hint', 'practice'].includes(body.outcome) ||
            !Number.isInteger(body.hints) || body.hints < 0 || body.hints > 2 || typeof body.student_saw_answer !== 'boolean' ||
            typeof body.answer !== 'string' || body.answer.length > 2000 || typeof body.note !== 'string' || body.note.length > 400) throw Error('Invalid answer record.');
        let ai_review = null;
        if (body.ai_review) {
          if (!global.RevisionTutor) throw Error('AI feedback could not be validated.');
          const q = this.bank.questions.find(q => q.id === body.question_id);
          const item = body.variant === 'main' ? q : q.retest;
          ai_review = global.RevisionTutor.validate(item, body.answer.trim(), body.ai_review);
        }
        if (body.elapsed_seconds !== undefined && (!Number.isInteger(body.elapsed_seconds) || body.elapsed_seconds < 0 || body.elapsed_seconds > 86400)) throw Error('Invalid timing record.');
        const payload = { ...(body.elapsed_seconds !== undefined ? {elapsed_seconds:body.elapsed_seconds} : {}), ...(ai_review ? { ai_review } : {}), student_id: 'practice-learner', question_id: body.question_id, question_version: this.bank.version,
          variant: body.variant, mode: body.mode, outcome: body.outcome === 'independent' && (body.hints || body.student_saw_answer) ? 'hint' : body.outcome,
          hints: body.hints, student_saw_answer: body.student_saw_answer, answer: body.answer.trim(), note: body.note.trim() };
        const event = this.append(body.id, 'answer_observed', payload);
        return { ...event.payload, id: event.event_id, created_at: event.recorded_at };
      }
      if (url.pathname === '/api/undo') {
        if (!body || !this.events().some(e => e.event_id === body.id && e.type === 'answer_observed')) throw Error('Observation not found.');
        this.append('retract-' + body.id, 'observation_retracted', { target_event_id: body.id, student_id: 'practice-learner' });
        return { ok: true };
      }
      throw Error('This feature is not available in the preview.');
    }
  }
  global.RevisionBrowserStore = RevisionBrowserStore;
  if (global.REVISION_CONFIG?.storage === 'browser') {
    global.revisionStoreReady = global.fetch('./question-bank.json').then(r => {
      if (!r.ok) throw Error('Could not load the practice questions.');
      return r.json();
    }).then(bank => { global.revisionStore = new RevisionBrowserStore(bank, global.localStorage); });
    // The initial request surfaces any load failure in the app's retry view.
    global.revisionStoreReady.catch(() => {});
  }
})(globalThis);
