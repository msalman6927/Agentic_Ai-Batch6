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

export type RegisterResponse = TokenPair & { user: User };

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

export type QuestionPayload = {
  question_id: string;
  difficulty: Difficulty;
  text: string;
  options: Record<OptionLetter, string>;
  thread_id: string | null;
};

export type ScoreEvent = { iq_score: number; level: Level };
export type PhaseEvent = { phase: Phase; question_index?: number | null; total?: number | null };
export type DoneEvent = { thread_id: string; phase: Phase };

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

export type StreamError = { code: ErrorCode; message: string; retryable: boolean };
export type ErrorEnvelope = { error: StreamError & { details: Record<string, unknown> } };
export type ChatMessageRequest = { topic: string; message: string } | { thread_id: string; message: string };
export type ChatAnswerRequest = { thread_id: string; question_id: string; option: OptionLetter };

export type StreamEvent = {
  event: string;
  data: unknown;
};
