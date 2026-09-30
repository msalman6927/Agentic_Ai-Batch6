import type {
  DoneEvent,
  Phase,
  PhaseEvent,
  QuestionPayload,
  ScoreEvent,
  StreamError,
  StreamEvent,
} from "./types";

export type StreamStatus = "idle" | "connecting" | "streaming" | "completed" | "failed";

export type ChatState = {
  threadId: string | null;
  phase: Phase;
  question: QuestionPayload | null;
  questionIndex: number | null;
  totalQuestions: number | null;
  score: ScoreEvent | null;
  assistantDraft: string;
  streamStatus: StreamStatus;
  streamError: StreamError | null;
};

export const initialChatState: ChatState = {
  threadId: null,
  phase: "idle",
  question: null,
  questionIndex: null,
  totalQuestions: null,
  score: null,
  assistantDraft: "",
  streamStatus: "idle",
  streamError: null,
};

type Action =
  | { type: "stream_started" }
  | { type: "event"; event: StreamEvent }
  | { type: "stream_incomplete"; message: string }
  | { type: "reset" };

export function chatReducer(state: ChatState, action: Action): ChatState {
  if (action.type === "reset") return initialChatState;
  if (action.type === "stream_started") {
    return { ...state, assistantDraft: "", streamError: null, streamStatus: "connecting" };
  }
  if (action.type === "stream_incomplete") {
    return {
      ...state,
      streamStatus: "failed",
      streamError: { code: "internal", message: action.message, retryable: true },
    };
  }

  const { event } = action;
  if (event.event === "phase") {
    const phase = event.data as PhaseEvent;
    return {
      ...state,
      phase: phase.phase,
      questionIndex: phase.question_index ?? state.questionIndex,
      totalQuestions: phase.total ?? state.totalQuestions,
      streamStatus: "streaming",
    };
  }
  if (event.event === "question") {
    const question = event.data as QuestionPayload;
    return {
      ...state,
      phase: "assessing",
      question,
      threadId: question.thread_id ?? state.threadId,
      streamStatus: "streaming",
    };
  }
  if (event.event === "score") {
    return { ...state, score: event.data as ScoreEvent, streamStatus: "streaming" };
  }
  if (event.event === "token") {
    const token = event.data as { delta: string };
    try {
      const parsed = JSON.parse(token.delta) as QuestionPayload;
      if (parsed.question_id && parsed.difficulty && parsed.text && parsed.options && parsed.thread_id) {
        return { ...state, phase: "assessing", question: parsed, threadId: parsed.thread_id, streamStatus: "streaming" };
      }
    } catch {
      // Normal explanation tokens are not JSON.
    }
    return { ...state, assistantDraft: state.assistantDraft + token.delta, streamStatus: "streaming" };
  }
  if (event.event === "done") {
    const done = event.data as DoneEvent;
    return {
      ...state,
      threadId: done.thread_id,
      phase: done.phase,
      question: done.phase === "follow_up" ? null : state.question,
      streamStatus: "completed",
    };
  }
  if (event.event === "error") {
    return { ...state, streamError: event.data as StreamError, streamStatus: "failed" };
  }
  return state;
}