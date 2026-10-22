# OCR Applied Science family revision

A small F181 **Science in society** practice app for a student and parent. Both solo practice and parent-led spoken questions contribute to one understanding record.

The record is an **append-only folder of JSON events**. Every observation creates a file; undo creates another event referencing the original. The app rebuilds the progress view from those files.

## GitHub Pages preview

The `Deploy GitHub Pages` Actions workflow publishes the static app on pushes to `main`. With repository Pages configured to **GitHub Actions**, the expected URL is <https://snowch.github.io/ocr-applied-science/>.

**The Pages preview saves observations only in the current browser.** It supports prepared questions, parent/self-check modes, hints, progress and JSON event backup, but does not synchronize between phones or connect to Google Drive. Clearing browser data removes those local records; use **Back up observations** to export them. No learner observations or API keys are uploaded to the public repository or deployed artifact.

GitHub Pages cannot run the Python API. The static preview uses a separate browser storage adapter; local server mode continues to use JSON event files. Shared family storage still needs an authenticated backend or a configured Google Drive integration.

## Try locally

Requires Python 3.10 or newer; the app has no third-party dependencies.

```sh
git clone https://github.com/snowch/ocr-applied-science.git
cd ocr-applied-science
python -m app.server
```

Open <http://127.0.0.1:8765>. The server deliberately listens only on loopback. Two browser sessions connected to that instance see the same practice learner.

Choose **Revise on my own** or **Ask together**. In a parent-led session, read the question aloud, consult the answer guide, and record **Explained independently**, **Needed a hint**, or **Needs practice**. Answers and notes are optional. The app saves the observation when an outcome is tapped.

## Understanding, with evidence

- Parent observations and student self-checks are labelled separately.
- Hints or disclosure of the answer prevent an attempt being recorded as independent.
- One correct answer does not establish mastery.
- A later-retest indicator requires recorded independent answers at least 24 hours apart, including a retest variant. It remains an observation-based indicator, not a validated mastery judgement.
- A later difficulty takes precedence in the current view; earlier observations remain in the history.
- A short summary can be reviewed before sharing through the device's share menu or copying into WhatsApp/email.

## Storage and privacy

Runtime events live under `data/events/`, excluded from Git. **This repository is public: do not commit learner records, names, account credentials, or API keys.** Prepared questions and application code belong here; private family observations belong in private runtime storage.

The local adapter atomically creates each event once, checks retry IDs, and never overwrites an event. This is append-only application behaviour, not tamper-proof or write-once storage. Someone with filesystem access can still change or delete files.

See [the event format and Drive design](docs/event-storage.md).

## Prepared content and AI experiments

`content/f181-question-bank.json` contains 20 original practice questions, marking points, model answers, hints, follow-ups and different retests. The bank covers selected F181 topics, not the full syllabus or live pre-release material. It was aligned to the [OCR specification, version 7.0, June 2026](https://www.ocr.org.uk/Images/697579-specification-cambridge-advanced-national-in-applied-science.pdf).

The practice rubrics are generated and await independent teacher review. They are not official OCR mark schemes. Official OCR PDFs are linked rather than redistributed here.

The current local app uses parent observations and self-checks. It does **not** call an AI API. The optional developer experiment below evaluates Mistral against prepared rubrics using synthetic answers:

```sh
python tools/evaluate_bank.py
```

It asks for an API key without displaying it and writes results under ignored `reports/`. It defaults to Mistral Small; set `F181_MARKER_MODEL=mistral-medium-latest` to test Medium. API calls may incur charges. Earlier synthetic runs matched 18/20 expected scores with Small and 20/20 with Medium after deterministic scoring checks; these do not establish official marking accuracy.

## Checks

```sh
python -m unittest discover -s tests -v
node --check app/static/app.js
node --test tests/browser-store.test.cjs
python tools/build_pages.py
```

Node is optional for running the app and is used only for the JavaScript syntax check.

## What remains for a phone-ready family app

- Hosted backend, separate family sign-ins and server-verified parent/student roles.
- Private Google Drive event storage, including authorization, retry handling and folder access.
- Browser/mobile interaction checks, installable PWA behaviour and offline/reconnection handling.
- Optional rubric-based AI marking with ambiguous answers routed for clarification.

Google Drive is not connected yet. The local prototype is not a publicly deployed or authenticated service. It must not be exposed directly to the internet.
