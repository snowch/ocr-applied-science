# Observation events

Each saved answer becomes one new JSON document. Reading events is necessary to show progress; “write only” here means **create new records without editing old records**, rather than denying every component read access.

The UI and any AI marker should use narrow backend operations. The AI does not need Drive credentials or permission to edit the event archive.

## Event envelope

```json
{
  "schema_version": 1,
  "event_id": "c74f1acf-0689-475f-a40e-bf0cef7fd314",
  "type": "answer_observed",
  "recorded_at": "2026-10-22T17:30:00+00:00",
  "payload_sha256": "computed SHA-256 of the canonical payload",
  "payload": {
    "student_id": "practice-learner",
    "question_id": "F181-P09",
    "question_version": "0.1",
    "variant": "main",
    "mode": "parent",
    "outcome": "hint",
    "hints": 1,
    "student_saw_answer": false,
    "answer": "Optional account of the explanation",
    "note": "Optional observation of the gap"
  }
}
```

This example is illustrative, not a learner record. `payload_sha256` is a checksum for accidental corruption; it does not authenticate the observer or prevent an administrator altering records. Parent/student mode is self-selected in the local prototype; hosted code must derive permitted roles and family membership from authenticated identity.

## Save and retry

The client generates an event UUID once for a save, retaining it across retries. The server validates the payload and adds its own timestamp. An identical retry returns the original event and timestamp. Reusing an ID for different content is rejected.

The filesystem adapter writes and fsyncs a staging file, then uses a no-replace hard link to publish the complete file. Readers see only published `*.json` files. They reject corrupt records rather than silently presenting incomplete progress. This requires a local filesystem supporting hard links and directory fsync; a Drive-synced local folder is not a substitute for a proper Drive API adapter.

## Corrections and undo

Undo appends an `observation_retracted` event with a `target_event_id`. The original bytes remain unchanged. Current progress excludes retracted observations; the event archive preserves the history. A corrected observation can then be saved with a new ID. Runtime privacy deletion, retention, or export policies can still require an administrator to remove personal data; append-only behaviour must not be treated as permission to retain it indefinitely.

## Google Drive adapter to implement

Use a private folder owned by the family and an authenticated backend. Expose observation creation and progress reading, without exposing generic file update/delete operations to the browser. Keep authorization credentials server-side. Users should interact through the app, not manually edit event files.

Drive editor access is **not** a create-only permission: the app can follow append-only rules while the underlying credential still permits edits. See [Drive roles](https://developers.google.com/workspace/drive/api/guides/ref-roles).

Drive permits duplicate filenames. Deduplicate by the event UUID, not the filename. A suitable implementation can allocate a [Drive file ID in advance](https://developers.google.com/workspace/drive/api/guides/create-file), persist it with the pending save and reuse it across upload retries. Concurrent use of one event ID must also be handled by the backend, rather than a race-prone list-then-create check.

Keep questions separate from observations. A future cached progress summary is disposable: it can be rebuilt from the event archive and a documented projection version. Refresh the view after successful saves and when another device returns to the app. A serverless deployment needs an external durable event store; its temporary local filesystem is insufficient.

## Current hosted adapter and learning evidence

The hosted app uses a dedicated Upstash hash, with each UUID field created using HSETNX. ACL permissions permit HGETALL/HGET/HSETNX on only that hash; they deny overwriting and deletion. Browser envelopes have no payload checksum; the earlier filesystem checksum is specific to the local adapter. Client timestamps are not authenticated and should not be interpreted as tamper-proof study evidence. Family roles are self-selected, with one private shared connection rather than separate authenticated accounts.

Version 1.0 preserves every pilot question ID. New F180/F181 IDs reference a skill and a canonical question-form ID. Linked retests reference another prepared form, so identical content cannot count twice towards the different-form requirement. Projections are rebuilt from all non-retracted observations. Current difficulty takes precedence and resets the independent-evidence sequence.

An answer payload may also contain `elapsed_seconds` (integer 0–86400) and `ai_review`. AI review fields include `source`, `status`, `met_points`, quoted `evidence`, code-calculated `score`, `max_marks`, `gap_tags`, `next_question`, and `model`. Unknown point IDs, unsupported quotes and inconsistent credit are rejected before saving. AI reviews remain suggestions alongside the self/parent outcome. Credentials never belong in an event. Retracting an observation removes both its human outcome and its AI suggestion from current projections, preserving the original bytes.

The Google Drive section above is historical design exploration and is not used by the current app.

`assessment_origin: "ai"` identifies an automatically derived outcome. For this source the client and local server require a validated attempted AI review and recompute the outcome, ignoring any supplied rating: full marks without recorded help yields `independent`, full marks with help yields `hint`, otherwise `practice`. Shared reads reject inconsistent AI-derived outcomes. Without this optional field, historical records remain manual judgements in the chosen mode. Ambiguous or unattempted AI reviews cannot create automatic outcomes.

## Teaching coverage events

A `teaching_status_changed` event has payload `student_id`, `skill_id`, `status` (`not_taught` or `ready`) and `mode` (`self` or `parent`). The envelope supplies the immutable event ID and recorded time. The latest event per skill controls coverage. These events are not attempts and do not add zero marks, failures or assessments. Marking ready appends a new event rather than changing the original; prior knowledge evidence remains intact. Not-taught skills are excluded from suggested/recommended/random practice and AI-coach priorities, but explicit manual selection remains available.
