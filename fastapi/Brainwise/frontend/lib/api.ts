import { parseSse } from "./sse";
import type {
  ChatAnswerRequest,
  ChatMessageRequest,
  ErrorEnvelope,
  Message,
  RegisterResponse,
  TokenPair,
  Topic,
  User,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8002";
const API_PREFIX = `${API_BASE_URL}/api/v1`;
const ACCESS_TOKEN_KEY = "brainwise.access";
const REFRESH_TOKEN_KEY = "brainwise.refresh";

export class ApiError extends Error {
  status: number;
  envelope?: ErrorEnvelope;

  constructor(status: number, message: string, envelope?: ErrorEnvelope) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.envelope = envelope;
  }
}

export function getStoredTokens(): TokenPair | null {
  if (typeof window === "undefined") return null;
  const access = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  const refresh = window.localStorage.getItem(REFRESH_TOKEN_KEY);
  return access && refresh ? { access, refresh } : null;
}

export function storeTokens(tokens: TokenPair) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh);
}

export function clearSession() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function parseError(response: Response): Promise<ApiError> {
  let envelope: ErrorEnvelope | undefined;
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    return new ApiError(response.status, response.statusText || "Request failed");
  }
  return new ApiError(response.status, envelope.error.message, envelope);
}

async function refreshTokens(): Promise<TokenPair> {
  const tokens = getStoredTokens();
  if (!tokens) throw new ApiError(401, "No refresh session available");
  const response = await fetch(`${API_PREFIX}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh: tokens.refresh }),
  });
  if (!response.ok) throw await parseError(response);
  const nextTokens = (await response.json()) as TokenPair;
  storeTokens(nextTokens);
  return nextTokens;
}

export async function refreshSession(): Promise<TokenPair> {
  return refreshTokens();
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const tokens = getStoredTokens();
  const headers = new Headers(init.headers);
  headers.set("Accept", headers.get("Accept") ?? "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (tokens) headers.set("Authorization", `Bearer ${tokens.access}`);

  const response = await fetch(`${API_PREFIX}${path}`, { ...init, headers });
  if (response.ok) {
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }
  if (response.status === 401 && retry && tokens) {
    try {
      await refreshTokens();
      return request<T>(path, init, false);
    } catch {
      clearSession();
    }
  }
  throw await parseError(response);
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  register: (payload: { email: string; password: string; name: string }) => request<RegisterResponse>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) => request<TokenPair>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request<User>("/auth/me"),
  topics: () => request<Topic[]>("/topics"),
  createTopic: (title: string) => request<Topic>("/topics", { method: "POST", body: JSON.stringify({ title }) }),
  messages: (topicId: string) => request<Message[]>(`/topics/${topicId}/messages`),
  deleteTopic: (topicId: string) => request<void>(`/topics/${topicId}`, { method: "DELETE" }),
  chat: (payload: ChatMessageRequest | ChatAnswerRequest, signal?: AbortSignal) => streamChat(payload, signal),
};

async function streamChat(payload: ChatMessageRequest | ChatAnswerRequest, signal?: AbortSignal, retry = true) {
  const tokens = getStoredTokens();
  if (!tokens) throw new ApiError(401, "You need to sign in first");
  const response = await fetch(`${API_PREFIX}/chat`, {
    method: "POST",
    signal,
    headers: {
      Authorization: `Bearer ${tokens.access}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (response.status === 401 && retry) {
      try {
        await refreshTokens();
        return streamChat(payload, signal, false);
      } catch {
        clearSession();
      }
    }
    throw await parseError(response);
  }
  if (!response.body) throw new Error("The server returned no stream body");
  return parseSse(response.body);
}
