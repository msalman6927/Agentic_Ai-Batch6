# Brainwise API Documentation

Frontend integration guide for Brainwise v1.

This document is the frontend-facing API contract. It describes the public HTTP API, authentication, topic history, the assessment state machine, the streaming chat protocol, error handling, and recommended client behavior.

## Contents

- [Quick Start](#quick-start)
- [API Conventions](#api-conventions)
- [Shared Types](#shared-types)
- [Authentication](#authentication)
- [Topics and History](#topics-and-history)
- [Chat and SSE](#chat-and-sse)
- [Assessment Workflow](#assessment-workflow)
- [Follow-up Workflow](#follow-up-workflow)
- [Errors](#errors)
- [Frontend State Management](#frontend-state-management)
- [TypeScript Models](#typescript-models)
- [Integration Checklist](#integration-checklist)
- [Scope and Limitations](#scope-and-limitations)

## Quick Start

### Base URL

All versioned endpoints use this prefix:

```text
/api/v1
```

Configure the deployment origin in the frontend instead of hard-coding it:

```ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
```

Example endpoint:

```text
POST http://localhost:8000/api/v1/auth/login
```

The backend's default development CORS origin is `http://localhost:3000`. Production frontend origins must be configured by the backend deployment.

### First request sequence

1. `POST /auth/register` or `POST /auth/login`.
2. Store the returned `access` and `refresh` tokens according to the frontend's security policy.
3. Send the access token as `Authorization: Bearer <access>` on protected requests.
4. When the access token expires, call `POST /auth/refresh` with the refresh token.
5. Use `POST /chat` to start an assessment, answer questions, generate the explanation, and send follow-ups.
6. Use `GET /topics` and `GET /topics/{topic_id}/messages` to restore the sidebar and conversation history.

## API Conventions

### Headers

JSON requests:

```http
Content-Type: application/json
Accept: application/json
```

Authenticated requests additionally require:

```http
Authorization: Bearer <access-token>
```

The chat response uses:

```http
Accept: text/event-stream
```

The backend also returns `Content-Type: text/event-stream` for a successful chat request.

### JSON and identifiers

- Request and response bodies are JSON unless the response is an SSE stream.
- IDs are UUID strings, for example `"12345678-1234-5678-1234-567812345678"`.
- Timestamps are ISO-8601 UTC strings, for example `"2026-09-30T14:25:10.123456Z"`.
- Enum values are case-sensitive in responses and lowercase unless otherwise stated.
- Request text is trimmed and NFC-normalized by the backend.
- Email addresses are trimmed, NFC-normalized, and lowercased by the backend.
- Unknown request properties are rejected. Do not send fields that are not documented for that request shape.
- Passwords are not trimmed or normalized. Send the exact password entered by the user.

### HTTP success statuses

| Status | Meaning |
|---:|---|
| `200` | Successful JSON response or successfully opened chat stream. |
| `204` | Topic was soft-deleted; response has no body. |

### Common response headers

The chat stream is sent with no-cache and buffering-disabled headers. Frontend code should consume chunks as they arrive and must not wait for the entire response before updating the UI.

### Health check

```http
GET /api/v1/health
```

This endpoint is public and does not require authentication.

Success: `200 OK`

```json
{
  "status": "ok"
}
```

Use this endpoint for a lightweight availability check. It does not authenticate a user and does not verify that a specific frontend session is valid.

## Shared Types

### Phases

A topic moves through these phases:

| Phase | Meaning | Frontend behavior |
|---|---|---|
| `idle` | No topic is currently active. | Show the new-topic entry state. |
| `topic_set` | Topic exists, but its assessment has not started. | A message can start the assessment. |
| `assessing` | The next multiple-choice answer is required. | Show the current question; disable free-text chat. |
| `scoring` | The third answer has been submitted and the score is being finalized. | Show scoring progress; do not accept another answer. |
| `explaining` | The calibrated explanation is streaming. | Render streamed assistant tokens. |
| `follow_up` | Assessment and explanation are complete. | Enable normal free-text chat. |

The server is authoritative for the current phase. Do not advance a topic locally until the stream confirms the transition.

### Assessment values

```text
Difficulty: easy | medium | hard
Option: A | B | C | D
Level: Foundation | Basic | Intermediate | Advanced
Role: user | assistant | system
```

Option input is normalized to uppercase, so `"b"` is accepted and emitted as `"B"` in server-controlled payloads.

### Score mapping

The score is computed by the backend, never by the frontend or language model:

| Correct answers | `iq_score` | `level` |
|---:|---:|---|
| 0 of 3 | 85 | `Foundation` |
| 1 of 3 | 95 | `Basic` |
| 2 of 3 | 110 | `Intermediate` |
| 3 of 3 | 128 | `Advanced` |

The API permits scores from 85 to 130, but the assessment currently emits only `85`, `95`, `110`, or `128`.

### Standard error envelope

Every non-stream error uses this shape:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Request validation failed",
    "details": {
      "fields": [
        {
          "loc": "body.email",
          "msg": "value is not a valid email address",
          "type": "value_error"
        }
      ]
    },
    "retryable": false
  }
}
```

The `details` object is always present. It may be empty. Validation errors include `details.fields`.

## Authentication

All authentication endpoints are under `/api/v1/auth`.

### Register

```http
POST /api/v1/auth/register
Content-Type: application/json
```

Request:

```json
{
  "email": "student@example.com",
  "password": "passw0rd1",
  "name": "Amina Student"
}
```

Rules:

- `email`: valid email address; trimmed and lowercased.
- `password`: 8-72 characters, must contain at least one letter and one digit, and must be at most 72 UTF-8 bytes.
- `name`: trimmed, non-empty, maximum 120 characters.
- Extra fields are rejected.

Success: `200 OK`

```json
{
  "access": "<jwt-access-token>",
  "refresh": "<jwt-refresh-token>",
  "user": {
    "id": "12345678-1234-5678-1234-567812345678",
    "email": "student@example.com",
    "name": "Amina Student",
    "created_at": "2026-09-30T14:25:10.123456Z"
  }
}
```

Duplicate email: `422 invalid_request` with a field error at `body.email`.

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json
```

Request:

```json
{
  "email": "student@example.com",
  "password": "passw0rd1"
}
```

Login passwords only require 1-72 characters. The registration composition rule is not re-applied during login.

Success: `200 OK`

```json
{
  "access": "<jwt-access-token>",
  "refresh": "<jwt-refresh-token>"
}
```

Wrong email or password: `401 invalid_credentials`.

### Refresh tokens

```http
POST /api/v1/auth/refresh
Content-Type: application/json
```

Request:

```json
{
  "refresh": "<jwt-refresh-token>"
}
```

Success: `200 OK`

```json
{
  "access": "<new-jwt-access-token>",
  "refresh": "<new-jwt-refresh-token>"
}
```

Refresh behavior:

- Access tokens last 30 minutes by default.
- Refresh tokens last 7 days by default.
- The refresh token must be a refresh token, not an access token.
- Refresh is stateless in v1. There is no server-side revocation list or logout endpoint.
- Expired, malformed, incorrectly typed, or account-invalid tokens return `401 unauthorized`.

### Current user

```http
GET /api/v1/auth/me
Authorization: Bearer <access-token>
```

Success: `200 OK`

```json
{
  "id": "12345678-1234-5678-1234-567812345678",
  "email": "student@example.com",
  "name": "Amina Student",
  "created_at": "2026-09-30T14:25:10.123456Z"
}
```

### Recommended token retry behavior

Use one refresh attempt for a failed authenticated request:

1. Receive `401 unauthorized`.
2. Call `/auth/refresh` with the stored refresh token.
3. Replace both stored tokens with the returned pair.
4. Retry the original request once.
5. If refresh or the retry fails, clear the session and send the user to login.

Do not retry indefinitely. Do not retry a chat request automatically after a stream has already started; use the chat resume rules instead.

## Topics and History

Topics are the user's study threads. All topic endpoints require an access token.

### List topics

```http
GET /api/v1/topics
Authorization: Bearer <access-token>
```

Success: `200 OK`

```json
[
  {
    "id": "12345678-1234-5678-1234-567812345678",
    "title": "Photosynthesis",
    "phase": "follow_up",
    "iq_score": 110,
    "level": "Intermediate",
    "updated_at": "2026-09-30T14:32:10.123456Z"
  },
  {
    "id": "87654321-4321-8765-4321-876543218765",
    "title": "Linear Algebra",
    "phase": "topic_set",
    "iq_score": null,
    "level": null,
    "updated_at": "2026-09-30T13:10:00.000000Z"
  }
]
```

Behavior:

- Only active topics owned by the current user are returned.
- Results are sorted by `updated_at` descending.
- A new topic starts at `topic_set` with `iq_score: null` and `level: null`.
- There is no pagination in v1.
- An account with no topics receives `[]`.

### Create a topic

```http
POST /api/v1/topics
Authorization: Bearer <access-token>
Content-Type: application/json
```

Request:

```json
{
  "title": "  Linear Algebra  "
}
```

Rules:

- `title` is trimmed and NFC-normalized.
- It must be non-empty and no longer than 200 characters.
- Extra fields are rejected.

Success: `200 OK`

```json
{
  "id": "87654321-4321-8765-4321-876543218765",
  "title": "Linear Algebra",
  "phase": "topic_set",
  "iq_score": null,
  "level": null,
  "updated_at": "2026-09-30T13:10:00.000000Z"
}
```

Creating a topic only creates the thread. It does not generate question 1. Start the assessment by sending a message to `/chat` with the topic's `thread_id`.

### List messages

```http
GET /api/v1/topics/{topic_id}/messages
Authorization: Bearer <access-token>
```

Success: `200 OK`

```json
[
  {
    "id": "11111111-1111-1111-1111-111111111111",
    "role": "user",
    "content": "Teach me photosynthesis",
    "phase": "topic_set",
    "created_at": "2026-09-30T14:20:00.000000Z"
  },
  {
    "id": "22222222-2222-2222-2222-222222222222",
    "role": "assistant",
    "content": "Photosynthesis is ...",
    "phase": "explaining",
    "created_at": "2026-09-30T14:21:00.000000Z"
  }
]
```

Behavior:

- Messages are sorted by `created_at` ascending.
- An empty topic returns `[]`.
- Each message includes the phase in which it was produced.
- The streamed assistant response is persisted after a successful stream completes.
- A failed partial stream is not persisted as a completed assistant message.

### Delete a topic

```http
DELETE /api/v1/topics/{topic_id}
Authorization: Bearer <access-token>
```

Success: `204 No Content` with an empty body.

Deletion is soft deletion. A deleted topic is not returned by list endpoints and cannot be loaded or used in chat.

A missing, deleted, or foreign topic returns the same response:

```http
404 Not Found
```

```json
{
  "error": {
    "code": "not_found",
    "message": "Topic not found",
    "details": {},
    "retryable": false
  }
}
```

This behavior prevents the API from revealing whether another user's topic exists.

## Chat and SSE

`POST /api/v1/chat` is the main Brainwise endpoint. It requires an access token and returns a streamed response.

### Why not `EventSource`?

Native browser `EventSource` only supports a GET request and cannot send the required JSON body. Use `fetch()` with a `ReadableStream` instead.

### Message mode: start or continue a conversation

Start a new topic directly:

```json
{
  "topic": "photosynthesis",
  "message": "Teach me photosynthesis"
}
```

Continue an existing thread:

```json
{
  "thread_id": "12345678-1234-5678-1234-567812345678",
  "message": "Can you give me another example?"
}
```

Exactly one of `topic` or `thread_id` is required. `message` is always required.

Rules:

- `topic`: non-empty, maximum 200 characters.
- `message`: non-empty, maximum 4000 characters.
- `thread_id`: valid UUID.
- Extra fields are rejected.
- During `assessing`, free-text messages are rejected with `409 invalid_phase`.
- During `topic_set`, the first message starts assessment and emits question 1.
- During `follow_up`, the message is sent to the follow-up agent.
- During `scoring` or `explaining`, a message resumes explanation generation.

### Answer mode

Submit the current assessment answer:

```json
{
  "thread_id": "12345678-1234-5678-1234-567812345678",
  "question_id": "33333333-3333-3333-3333-333333333333",
  "option": "B"
}
```

Rules:

- All three fields are required.
- `thread_id` and `question_id` must be valid UUIDs.
- `option` must be `A`, `B`, `C`, or `D`. Lowercase input is accepted and normalized.
- Do not send `message` or `topic` in answer mode.
- The question must belong to the authenticated user's thread and be the current assessment question.

### Starting the stream

```ts
const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  },
  body: JSON.stringify(payload),
});

if (!response.ok) {
  const error = await response.json();
  throw new ApiError(response.status, error);
}

if (!response.body) {
  throw new Error("The server returned no stream body");
}
```

A successful chat request returns `200 OK` immediately and then streams frames. Errors detected before the first frame return a normal HTTP error response instead.

### SSE wire format

Each frame has this exact structure and ends with a blank line:

```text
event: phase
data: {"phase":"assessing","question_index":1,"total":3}

```

The JSON data is on one line. A parser must support multiple network chunks making up one frame. Never assume one `ReadableStream` chunk equals one SSE frame.

### Recommended SSE parser

```ts
type StreamEvent = {
  event: string;
  data: unknown;
};

async function* parseSse(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        if (!frame.trim()) continue;

        let event = "message";
        let dataText = "";
        for (const line of frame.split(/\r?\n/)) {
          if (line.startsWith("event: ")) event = line.slice(7);
          if (line.startsWith("data: ")) dataText += line.slice(6);
        }

        if (dataText) {
          yield { event, data: JSON.parse(dataText) };
        }
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      throw new Error("Incomplete SSE frame");
    }
  } finally {
    reader.releaseLock();
  }
}
```

Production code should also use an `AbortController` to cancel a stream when the user leaves the page or selects another thread.

## SSE Events

### `phase`

```json
{
  "phase": "assessing",
  "question_index": 1,
  "total": 3
}
```

Fields:

- `phase`: current server phase.
- `question_index`: present for assessment phases, normally `1`, `2`, or `3`.
- `total`: present for assessment phases and equal to `3`.

Scoring and explanation phase events may omit `question_index` and `total`.

### `question`

```json
{
  "question_id": "33333333-3333-3333-3333-333333333333",
  "difficulty": "medium",
  "text": "What is the primary purpose of chlorophyll?",
  "options": {
    "A": "To absorb light energy",
    "B": "To store genetic information",
    "C": "To digest proteins",
    "D": "To transport oxygen"
  },
  "thread_id": "12345678-1234-5678-1234-567812345678"
}
```

The frontend must display the question's `text` and all four options. The correct option is never sent to the frontend.

Question behavior:

- Question 1 is `medium` difficulty.
- If the previous answer is correct, the next question is `hard`.
- If the previous answer is wrong, the next question is `easy`.
- Exactly three questions are asked.
- The frontend must not calculate correctness or difficulty progression.

### `score`

```json
{
  "iq_score": 110,
  "level": "Intermediate"
}
```

The score is emitted after the final answer and before explanation tokens. Display the score and level independently; do not parse them from assistant text.

### `token`

```json
{
  "delta": "Photosynthesis is "
}
```

Append each `delta` to the current assistant draft in arrival order. A token event is not a complete message and must not create a separate message bubble.

### `done`

```json
{
  "thread_id": "12345678-1234-5678-1234-567812345678",
  "phase": "follow_up"
}
```

`done` is the successful terminal event. A healthy stream contains exactly one terminal event: either `done` or `error`.

### `error`

```json
{
  "code": "internal",
  "message": "Something went wrong while generating a response",
  "retryable": false
}
```

`error` is the failed terminal event. No events should be processed after it. Partial token text may already be visible, but it must not be committed to the conversation as a completed assistant message.

## Assessment Workflow

### Flow 1: Start with a new topic

Request:

```http
POST /api/v1/chat
Authorization: Bearer <access-token>
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "topic": "photosynthesis",
  "message": "Teach me photosynthesis"
}
```

Expected event order:

```text
phase  {"phase":"assessing","question_index":1,"total":3}
question {question 1 payload}
done   {"thread_id":"...","phase":"assessing"}
```

The `thread_id` in the question and done events is the newly created thread ID. Store it immediately, even if the connection later drops.

### Flow 2: Start assessment on an existing topic

First create a topic with `POST /topics`, then send:

```json
{
  "thread_id": "87654321-4321-8765-4321-876543218765",
  "message": "Begin my assessment"
}
```

The event sequence is the same as Flow 1. The topic changes from `topic_set` to `assessing`.

### Flow 3: Submit question 1 or 2

Request:

```json
{
  "thread_id": "12345678-1234-5678-1234-567812345678",
  "question_id": "33333333-3333-3333-3333-333333333333",
  "option": "B"
}
```

Expected event order:

```text
phase    {"phase":"assessing","question_index":2,"total":3}
question {question 2 payload}
done     {"thread_id":"...","phase":"assessing"}
```

The answer is graded and stored before the next question is generated. The result does not reveal whether the answer was correct.

### Flow 4: Submit question 3

The final answer produces:

```text
phase  {"phase":"scoring"}
phase  {"phase":"explaining"}
score  {"iq_score":110,"level":"Intermediate"}
token  {"delta":"..."}
token  {"delta":"..."}
...
done   {"thread_id":"...","phase":"follow_up"}
```

The explanation is streamed as Markdown text. Render it as Markdown only after applying the frontend's normal sanitization policy.

When `done` arrives:

- finalize the assistant message draft;
- mark the thread `follow_up`;
- enable the normal message composer;
- clear the assessment question state;
- optionally refresh `/topics` and `/topics/{id}/messages`.

### Assessment answer errors

- Sending a message instead of an answer while `assessing`: `409 invalid_phase`.
- Sending an answer for the wrong thread/question: `404 not_found` or a domain error envelope, depending on the failed ownership/current-question check.
- Sending an already answered question: normally `409 already_answered`.
- Sending an invalid option: `422 invalid_request`.
- Question generation failure before streaming: HTTP error envelope, usually `422 unsupported_topic` or `500 internal`.

## Explanation Resume

If the connection drops while the thread is `explaining`, the server leaves the thread resumable. To resume, send a normal message request using the same `thread_id`:

```json
{
  "thread_id": "12345678-1234-5678-1234-567812345678",
  "message": "Please continue the explanation."
}
```

The backend regenerates the explanation and emits:

```text
phase  {"phase":"explaining"}
score  {"iq_score":110,"level":"Intermediate"}
token  {"delta":"..."}
...
done   {"thread_id":"...","phase":"follow_up"}
```

A resumed explanation does not emit a second `scoring` phase event. The score is already stored.

The frontend should:

1. Keep the partial draft marked as incomplete.
2. Show a retry/resume action if the connection ends without `done` or `error`.
3. Reload history if needed before retrying.
4. Start a fresh assistant draft for the resumed explanation rather than silently concatenating two attempts.
5. Replace the incomplete draft with the completed server history after the resumed stream succeeds.

## Follow-up Workflow

Once the thread is `follow_up`, send normal message mode:

```json
{
  "thread_id": "12345678-1234-5678-1234-567812345678",
  "message": "What is chlorophyll?"
}
```

Expected event order:

```text
token  {"delta":"Chlorophyll "}
token  {"delta":"is ..."}
...
done   {"thread_id":"...","phase":"follow_up"}
```

Follow-up streams normally do not emit `phase` or `score` events. The thread remains in `follow_up`.

The backend may emit tool-generated events during follow-up in future-compatible implementations. A generic client should route unknown non-terminal events through an event handler rather than crashing, while the v1 documented events are `token` and `done`.

## Errors

### Error codes

| Code | Typical HTTP status | Retryable | Frontend action |
|---|---:|:---:|---|
| `unauthorized` | 401 | No | Refresh once; otherwise sign out. |
| `invalid_credentials` | 401 | No | Show a login error; do not retry automatically. |
| `forbidden` | 403 | No | Show an access-denied state. |
| `not_found` | 404 | No | Remove stale topic or show not-found state. |
| `invalid_phase` | 409 | No | Refresh topic state and show the correct control. |
| `already_answered` | 409 | No | Reload the current assessment state; do not double-submit. |
| `unsupported_topic` | 422 | Yes | Let the user rephrase or choose another topic. |
| `rate_limited` | 429 | Yes | Back off and offer retry. |
| `invalid_request` | 422 | No | Show field-level validation errors. |
| `internal` | 500 | Usually no | Show a generic failure and offer controlled retry. |

The `retryable` property on the response is authoritative. For an SSE error event, use that field instead of assuming all `5xx` errors are retryable.

### Validation errors

Example:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Request validation failed",
    "details": {
      "fields": [
        {
          "loc": "body.message",
          "msg": "String should have at least 1 character",
          "type": "string_too_short"
        }
      ]
    },
    "retryable": false
  }
}
```

Use `loc` to associate an error with a form field. Common locations include:

```text
body.email
body.password
body.name
body.title
body.message
body.thread_id
body.question_id
body.option
path.topic_id
```

### HTTP errors versus stream errors

Errors before the first SSE frame are ordinary HTTP responses:

```text
HTTP/1.1 409 Conflict
Content-Type: application/json
```

Errors after the first frame are SSE events. The HTTP response has already started with `200`, so the frontend must inspect the terminal event:

```text
event: error
data: {"code":"internal","message":"...","retryable":false}

```

Never treat an HTTP `200` chat response as a successful completed operation until `done` has been received.

## Frontend State Management

A practical client can maintain one state per active thread:

```text
idle
  -> topic_set
  -> assessing
  -> scoring
  -> explaining
  -> follow_up
```

### Suggested state shape

```ts
type ChatState = {
  threadId: string | null;
  phase: Phase;
  question: QuestionPayload | null;
  questionIndex: number | null;
  score: ScoreEvent | null;
  assistantDraft: string;
  streamStatus: "idle" | "connecting" | "streaming" | "completed" | "failed";
  streamError: StreamError | null;
};
```

### Event reducer rules

| Event | State update |
|---|---|
| `phase` | Set `phase`; set `questionIndex` and total when supplied. |
| `question` | Store the question, thread ID, and difficulty; clear any prior question draft. |
| `score` | Store `iq_score` and `level`; show score UI. |
| `token` | Append `delta` to the current assistant draft. |
| `done` | Mark stream complete; set the confirmed phase and finalize the draft. |
| `error` | Mark stream failed; preserve partial draft separately; do not finalize it as history. |
| Unknown event | Log or ignore safely; do not break the stream parser. |

### UI behavior by phase

- `topic_set`: show a start-learning composer.
- `assessing`: show exactly four answer buttons; disable the free-text composer and prevent duplicate submission while waiting.
- `scoring`: show a short score-processing state; disable answer and text controls.
- `explaining`: show the score, streaming Markdown, cancel/retry affordance, and disabled duplicate submit controls.
- `follow_up`: show the finalized explanation and enable free-text follow-ups.

### Duplicate submissions

Disable the selected answer immediately while its request is in progress. If the user retries after a network failure, reuse the same `question_id` and selected option only after checking the current thread state. Do not send multiple concurrent answer requests for one question.

### History reconciliation

For the most reliable UI:

- Use streaming events for immediate rendering.
- Use `GET /topics/{id}/messages` after a completed workflow or when recovering a dropped connection.
- Treat history as the persisted source of truth.
- Keep an incomplete streaming draft out of the persisted message list until `done` confirms success.

## TypeScript Models

```ts
export type Phase =
  | "idle"
  | "topic_set"
  | "assessing"
  | "scoring"
  | "explaining"
  | "follow_up";

export type Difficulty = "easy" | "medium" | "hard";
export type Level = "Foundation" | "Basic" | "Intermediate" | "Advanced";
export type OptionLetter = "A" | "B" | "C" | "D";
export type MessageRole = "user" | "assistant" | "system";

export type User = {
  id: string;
  email: string;
  name: string;
  created_at: string;
};

export type TokenPair = {
  access: string;
  refresh: string;
};

export type RegisterResponse = TokenPair & {
  user: User;
};

export type Topic = {
  id: string;
  title: string;
  phase: Phase;
  iq_score: number | null;
  level: Level | null;
  updated_at: string;
};

export type Message = {
  id: string;
  role: MessageRole;
  content: string;
  phase: Phase;
  created_at: string;
};

export type QuestionOptions = Record<OptionLetter, string>;

export type QuestionPayload = {
  question_id: string;
  difficulty: Difficulty;
  text: string;
  options: QuestionOptions;
  thread_id: string | null;
};

export type ScoreEvent = {
  iq_score: number;
  level: Level;
};

export type PhaseEvent = {
  phase: Phase;
  question_index?: number | null;
  total?: number | null;
};

export type DoneEvent = {
  thread_id: string;
  phase: Phase;
};

export type StreamError = {
  code: ErrorCode;
  message: string;
  retryable: boolean;
};

export type ErrorCode =
  | "unauthorized"
  | "invalid_credentials"
  | "forbidden"
  | "not_found"
  | "invalid_phase"
  | "already_answered"
  | "unsupported_topic"
  | "rate_limited"
  | "invalid_request"
  | "internal";

export type ErrorEnvelope = {
  error: StreamError & {
    details: Record<string, unknown>;
  };
};

export type ChatMessageRequest =
  | { topic: string; message: string }
  | { thread_id: string; message: string };

export type ChatAnswerRequest = {
  thread_id: string;
  question_id: string;
  option: OptionLetter;
};
```

## Integration Checklist

### Authentication

- [ ] Configure `API_BASE_URL` per environment.
- [ ] Register or login and store both tokens.
- [ ] Add the access bearer header to protected requests.
- [ ] Implement one refresh attempt for `401 unauthorized`.
- [ ] Clear session state when refresh fails.

### Topics

- [ ] Load topic list on authenticated app startup.
- [ ] Sort only for display if needed; the API already returns newest first.
- [ ] Create topics with a title no longer than 200 characters.
- [ ] Load message history in ascending order.
- [ ] Handle `204` delete responses without parsing JSON.
- [ ] Treat `404` as both stale-topic and ownership-safe not-found.

### Assessment

- [ ] Start via topic mode or an existing `topic_set` thread.
- [ ] Store `thread_id` from the first question event immediately.
- [ ] Render exactly four options.
- [ ] Submit only the current question ID.
- [ ] Disable duplicate answer submissions.
- [ ] Trust the server's phase, difficulty, score, and level.
- [ ] Never expose or infer the correct answer.

### Streaming

- [ ] Use `fetch`, `ReadableStream`, and an SSE parser.
- [ ] Handle arbitrary network chunk boundaries.
- [ ] Append token deltas into one draft.
- [ ] Require exactly one terminal `done` or `error`.
- [ ] Treat `200` without `done` as incomplete.
- [ ] Abort streams when leaving a thread or unmounting the screen.
- [ ] Resume incomplete explanations using the same thread ID.
- [ ] Reconcile with message history after completion or recovery.

### UI quality

- [ ] Show clear loading states for auth, topic loading, answer submission, scoring, and streaming.
- [ ] Keep the answer controls stable while the next question loads.
- [ ] Render explanation Markdown safely.
- [ ] Preserve partial text when displaying a failure, but label it incomplete.
- [ ] Show field-level validation messages from `details.fields`.
- [ ] Provide a controlled retry action for retryable errors.
- [ ] Do not allow free-text messages during assessment.

## Scope and Limitations

Brainwise v1 intentionally does not expose:

- file uploads;
- retrieval-augmented generation or user documents;
- image generation;
- voice input or output;
- multi-language model output;
- pagination or search endpoints;
- WebSocket transport;
- a logout endpoint or refresh-token revocation;
- a separate assessment-results endpoint;
- an endpoint exposing the correct answer or raw correctness per question.

The frontend should use the documented routes only. Internal SQLAlchemy models, agent tools, prompts, database tables, and provider configuration are not frontend APIs.
