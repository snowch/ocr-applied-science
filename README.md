# OCR Applied Science family exam coach

A shared revision app for one student and two parents, focused on the **F180 and F181 written exams** of OCR Cambridge Advanced National Applied Science H151. The live app is <https://snowch.github.io/ocr-applied-science/>. GitHub Actions deploys pushes to `main`.

## Practice and learning evidence

The bank contains **460 question entries: 320 F180 and 140 F181**. It includes four related forms for each of 110 new skills (recall, application, misconception correction and a combined response) plus the preserved 20-question pilot. Integrated forms reuse recall/application components. Linked retests reuse another form and are not counted as extra questions. They are not guaranteed unseen; the learning model identifies linked copies as the same item.

Every detailed teaching-content reference in the 15 topic areas has starter practice, including the six F180 practicals. This is **not exhaustive coverage of every breadth-and-depth bullet**, nor a replacement for diagrams, photographic interpretation, official papers or teacher feedback. All generated scientific content and marking guides remain provisional pending independent subject-teacher review. F181 exam-series pre-release material has not been selected. See [the coverage map](docs/exam-coverage.md) and [machine-readable coverage](content/exam-coverage.json).

Choose both units or one unit, then practise alone, ask together, or try a timed question. Timed practice hides hints and the guide until the independent answer is finished. Marking remains a parent observation or student self-check; elapsed time is recorded separately. A prepared explanation and worked example support gap repair.

Understanding tracks each skill's dated evidence. A latest supported/incomplete answer reopens a gap. Secure evidence requires at least three different question forms on three different dates spanning seven days, including an independent application response, all since the last difficulty. Hints and answer disclosure prevent an independent observation. This is an evidence indicator, **not a validated mastery judgement or predicted grade**. The scheduler prioritises due gaps, delayed checks and untested areas, avoiding immediate repetition and maintaining breadth across units. Same-day repetition or linked duplicate prompts cannot satisfy the different-item requirement. Combined responses reuse components and do not count as another distinct form.

## Settings: family storage

Open **Settings → Family storage** and import the same private Upstash connection JSON on each phone. Alternatively enter a REST URL, restricted token and `f181:events` key. No Google setup is required. The historic key name is retained across both units so existing observations survive the upgrade.

The connection JSON contains `url`, `token`, `key` and optional `trial_expires`. Configure a dedicated Upstash ACL user with `-@all +hgetall +hget +hsetnx` and `~f181:events`. Upstash requires a password from `ACL GENTOKEN username`; use that returned token as both password and REST bearer token. Do not use the database owner token in the app. The family token permits reading all family observations and adding new ones; it does not identify which family member saved them.

Each observation is a new hash field created using HSETNX. Undo adds a retraction; the restricted token cannot overwrite or delete original records. Database owners retain administrative access. Each device caches records locally and retries pending saves. The banner distinguishes confirmed sync from offline/pending saves. Refresh Understanding to see another device's changes. Device-only history stays separate on connecting, and switching stores does not copy records between families. Disconnect is blocked while saves are pending. Back up before clearing browser data.

## Settings: Mistral tutor

Open **Settings → Mistral tutor**, enter an API key, choose Small or Medium, then **Test and connect**. Keys stay in session storage by default; remembering in local storage is optional on trusted devices. Keys are never written to family storage or the public repository. API reviews use credits and happen only on request.

- **Get Mistral feedback**, while answering, sends the current question, rubric and written/transcribed answer. Mistral suggests rubric points, exact supporting quotations, gap categories and a probing follow-up. Code validates point IDs and quotations and calculates the score; model-provided totals are not trusted. Ambiguous answers require clarification. Changed answers invalidate earlier feedback. The user can discard an incorrect AI suggestion and judge against the guide.
- **Ask Mistral to review progress**, in Understanding, sends aggregate skill histories, outcomes, AI gap tags and suggested scores. It compares progress over time and proposes up to three known skills and an actionable next session. Detailed past answers, parent notes and storage credentials are not sent. Advice cannot overwrite evidence statuses, and fabricated skill IDs are rejected.
- Saved answer reviews are explicitly labelled **AI suggestions**, separately from parent/student outcomes. They sync with the observation, allowing all three devices to see the evidence. Oral answers need a brief transcription for AI marking. AI-generated follow-ups can be asked aloud and recorded in the note; they are not automatically marked.

AI scientific/marking accuracy across the expanded bank has not been independently established. No full-bank live Mistral evaluation was run during this upgrade; request formatting, validation and UI paths are tested with synthetic responses.

## Local development and checks

Requires Python 3.10+; runtime has no third-party dependencies. `python -m app.server` serves <http://127.0.0.1:8765> on loopback only, with append-only JSON events in ignored `data/events/`. Do not expose that development server publicly. The hosted app uses browser/Upstash storage instead.

```sh
python tools/build_question_bank.py
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
node --check app/static/app.js
node --check app/static/tutor.js
python tools/build_pages.py
```

Source seeds are in `content/source/`. Rebuilding is deterministic and uses no API. Original OCR documents are linked, not redistributed. The older `content/f181-question-bank.json` remains for the original synthetic marking experiment in `tools/evaluate_bank.py`.

For an isolated live sync check set `F181_LIVE_CONNECTION` to a private JSON connection using a separate `f181:test:events` key and matching restricted token. Never use real learner records in tests.

This public repository must never contain private connection files, API keys or learner observations. The app is responsive web software; installation, service-worker offline loading, physical iOS/Android validation, full mock-paper delivery and individual authenticated accounts are not yet implemented. Local-first observation queues work while an already loaded app is offline.
