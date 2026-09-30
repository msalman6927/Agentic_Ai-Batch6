"use client";

import { FormEvent, useEffect, useReducer, useState } from "react";
import { api, ApiError, clearSession, getStoredTokens, storeTokens } from "../lib/api";
import { chatReducer, initialChatState } from "../lib/chat-reducer";
import type { Message, OptionLetter, Topic, User } from "../lib/types";

type AuthMode = "login" | "register";

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [activeTopic, setActiveTopic] = useState<Topic | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chat, dispatch] = useReducer(chatReducer, initialChatState);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [mobileRailOpen, setMobileRailOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [topicDraft, setTopicDraft] = useState("");
  const [showTopicForm, setShowTopicForm] = useState(false);
  const [deletingTopicId, setDeletingTopicId] = useState<string | null>(null);
  const [selectedOption, setSelectedOption] = useState<OptionLetter | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function initializeSession() {
      if (!getStoredTokens()) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const [currentUser, availableTopics] = await Promise.all([api.me(), api.topics()]);
        if (cancelled) return;
        setUser(currentUser);
        setTopics(availableTopics);
        if (availableTopics[0]) {
          setActiveTopic(availableTopics[0]);
          const history = await api.messages(availableTopics[0].id);
          const restoredQuestion = history.map((item) => parseQuestionMessage(item.content)).reverse().find(Boolean);
          setMessages(history.filter((item) => !parseQuestionMessage(item.content)));
          if (restoredQuestion) dispatch({ type: "event", event: { event: "question", data: restoredQuestion } });
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof ApiError ? cause.message : "Could not restore your session.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void initializeSession();
    return () => {
      cancelled = true;
    };
  }, []);

  async function hydrateSession() {
    try {
      const [currentUser, availableTopics] = await Promise.all([api.me(), api.topics()]);
      setUser(currentUser);
      setTopics(availableTopics);
      if (availableTopics[0]) await selectTopic(availableTopics[0]);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not restore your session.");
    } finally {
      setLoading(false);
    }
  }

  async function selectTopic(topic: Topic) {
    setActiveTopic(topic);
    dispatch({ type: "reset" });
    setError("");
    try {
      const history = await api.messages(topic.id);
      const restoredQuestion = history.map((item) => parseQuestionMessage(item.content)).reverse().find(Boolean);
      setMessages(history.filter((item) => !parseQuestionMessage(item.content)));
      if (restoredQuestion) dispatch({ type: "event", event: { event: "question", data: restoredQuestion } });
    } catch (cause) {
      setMessages([]);
      setError(cause instanceof ApiError ? cause.message : "Could not load this topic.");
    }
  }

  async function createTopic(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = topicDraft.trim();
    if (!title || working) return;
    setWorking(true);
    setError("");
    try {
      const topic = await api.createTopic(title);
      setTopics((current) => [topic, ...current]);
      setTopicDraft("");
      setShowTopicForm(false);
      await selectTopic(topic);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not create this topic.");
    } finally {
      setWorking(false);
    }
  }

  async function deleteTopic(topic: Topic) {
    if (deletingTopicId || !window.confirm(`Delete the topic \"${topic.title}\"?`)) return;
    setDeletingTopicId(topic.id);
    try {
      await api.deleteTopic(topic.id);
      const remaining = topics.filter((item) => item.id !== topic.id);
      setTopics(remaining);
      if (activeTopic?.id === topic.id) {
        setActiveTopic(remaining[0] ?? null);
        setMessages(remaining[0] ? await api.messages(remaining[0].id) : []);
        dispatch({ type: "reset" });
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not delete this topic.");
    } finally {
      setDeletingTopicId(null);
    }
  }

  async function consumeChat(payload: Parameters<typeof api.chat>[0]) {
    setWorking(true);
    setError("");
    dispatch({ type: "stream_started" });
    let completed = false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 90000);
    try {
      const stream = await api.chat(payload, controller.signal);
      for await (const event of stream) {
        if (event.event === "done") completed = true;
        dispatch({ type: "event", event });
      }
      if (!completed) {
        dispatch({ type: "stream_incomplete", message: "The stream ended before Brainwise confirmed completion." });
      } else if (activeTopic) {
        const history = await api.messages(activeTopic.id);
        const restoredQuestion = history.map((item) => parseQuestionMessage(item.content)).reverse().find(Boolean);
        setMessages(history.filter((item) => !parseQuestionMessage(item.content)));
        if (restoredQuestion) dispatch({ type: "event", event: { event: "question", data: restoredQuestion } });
      } else {
        const refreshedTopics = await api.topics();
        setTopics(refreshedTopics);
        if (refreshedTopics[0]) setActiveTopic(refreshedTopics[0]);
      }
    } catch (cause) {
      const message = cause instanceof DOMException && cause.name === "AbortError"
        ? "The backend took too long to prepare the next step. Please retry."
        : cause instanceof ApiError
          ? cause.message
          : "The connection was interrupted. Please try again.";
      setError(message);
      dispatch({ type: "stream_incomplete", message: "The connection was interrupted." });
    } finally {
      window.clearTimeout(timeoutId);
      setWorking(false);
    }
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const name = String(form.get("name") ?? "");
    try {
      const tokens = mode === "register" ? await api.register({ email, password, name }) : await api.login({ email, password });
      storeTokens(tokens);
      await hydrateSession();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Authentication failed.");
    }
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setTopics([]);
    setActiveTopic(null);
    setMessages([]);
    dispatch({ type: "reset" });
    setError("");
  }

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || working || chat.phase === "assessing") return;
    setMessages((current) => [...current, { id: `local-${Date.now()}`, role: "user", content: trimmed, phase: activeTopic?.phase ?? "topic_set", created_at: new Date().toISOString() }]);
    setMessage("");
    if (activeTopic) await consumeChat({ thread_id: activeTopic.id, message: trimmed });
    else await consumeChat({ topic: trimmed, message: `Teach me ${trimmed}` });
  }

  async function handleAnswer(option: OptionLetter) {
    if (!chat.question || !chat.threadId || working) return;
    setSelectedOption(option);
    await consumeChat({ thread_id: chat.threadId, question_id: chat.question.question_id, option });
    setSelectedOption(null);
  }

  const [mode, setMode] = useState<AuthMode>("login");

  if (loading) return <div className="grid min-h-screen place-items-center bg-[var(--background)] text-sm text-[var(--ink-soft)]">Loading your workspace...</div>;
  if (!user) return <AuthScreen mode={mode} setMode={setMode} onSubmit={handleAuth} error={error} />;

  const question = chat.question;
  const displayMessages = messages.length ? messages : [];
  return <main className="min-h-screen bg-[var(--background)] text-[var(--foreground)]"><div className="mx-auto flex min-h-screen max-w-[1600px] overflow-hidden border-x border-[var(--line)] bg-[var(--panel)]">
    <aside className={`fixed inset-y-0 left-0 z-20 flex w-[290px] -translate-x-full flex-col border-r border-[var(--line)] bg-[#f8f9f5] p-5 transition-transform lg:static lg:translate-x-0 ${mobileRailOpen ? "translate-x-0" : ""}`}>
      <div className="flex items-center justify-between"><a href="#top" className="flex items-center gap-3" aria-label="Brainwise home"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--teal)] text-lg font-bold text-white">B</span><span className="display-font text-[22px] font-semibold tracking-[-0.03em]">brainwise</span></a><button className="rounded-lg p-2 text-xl text-[var(--ink-soft)] hover:bg-[var(--mint)] lg:hidden" onClick={() => setMobileRailOpen(false)} aria-label="Close navigation">x</button></div>
      <button className="mt-9 flex items-center justify-center gap-2 rounded-xl border border-dashed border-[#b8c9c0] bg-white px-4 py-3 text-sm font-semibold text-[var(--teal-deep)] transition hover:border-[var(--teal)] hover:bg-[var(--mint)]" onClick={() => { setShowTopicForm(true); setError(""); }}><span className="text-lg leading-none">+</span> New topic</button>
      {showTopicForm && <form onSubmit={createTopic} className="mt-3 rounded-xl border border-[var(--line)] bg-white p-3"><label htmlFor="topic-title" className="text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--ink-soft)]">Topic name</label><input id="topic-title" autoFocus required maxLength={200} value={topicDraft} onChange={(event) => setTopicDraft(event.target.value)} placeholder="e.g. Cell biology" className="mt-2 w-full rounded-lg border border-[var(--line)] px-3 py-2 text-sm outline-none focus:border-[var(--teal)]" /><div className="mt-2 flex gap-2"><button type="submit" disabled={working} className="flex-1 rounded-lg bg-[var(--teal)] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Create</button><button type="button" onClick={() => setShowTopicForm(false)} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--ink-soft)]">Cancel</button></div></form>}
      <div className="mt-9 flex items-center justify-between px-1"><span className="text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--ink-soft)]">Your topics</span><span className="rounded-full bg-[#e8eee8] px-2 py-0.5 text-[11px] font-bold text-[var(--ink-soft)]">{topics.length.toString().padStart(2, "0")}</span></div>
      <nav className="scrollbar-thin mt-3 space-y-1 overflow-y-auto" aria-label="Topics">{topics.map((topic) => <div key={topic.id} className={`group flex items-center rounded-xl transition ${activeTopic?.id === topic.id ? "bg-[var(--mint)]" : "hover:bg-[#edf1eb]"}`}><button onClick={() => void selectTopic(topic)} className="min-w-0 flex-1 px-3 py-3 text-left"><span className="flex items-center gap-2 truncate text-[14px] font-semibold">{activeTopic?.id === topic.id && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--teal)]" />}{topic.title}</span><span className="mt-1 block pl-3.5 text-[11px] text-[var(--ink-soft)]">{topic.level ?? topic.phase}</span></button><button onClick={() => void deleteTopic(topic)} disabled={deletingTopicId === topic.id} className="mr-2 rounded-md px-2 py-1 text-xs text-[var(--ink-soft)] opacity-0 transition hover:bg-[var(--coral-soft)] hover:text-[var(--coral)] group-hover:opacity-100 disabled:opacity-50" aria-label={`Delete ${topic.title}`}>x</button></div>)}</nav>
      <div className="mt-auto rounded-2xl bg-[var(--teal-deep)] p-4 text-white"><div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.12em] text-[#a7d6c9]"><span>Connection</span><span>Online</span></div><p className="mt-3 text-xs leading-5 text-[#d2e9e1]">Connected to the Brainwise learning service.</p></div>
      <div className="mt-4 flex items-center gap-3 rounded-xl p-2"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#f0cfa3] text-xs font-bold text-[#704a20]">{user.name.slice(0, 2).toUpperCase()}</span><span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{user.name}</span><span className="block truncate text-[11px] text-[var(--ink-soft)]">{user.email}</span></span><button onClick={handleLogout} className="rounded-lg px-2 py-1 text-[11px] font-semibold text-[var(--ink-soft)] hover:bg-[var(--coral-soft)] hover:text-[var(--coral)]" aria-label="Log out">Logout</button></div>
    </aside>
    {mobileRailOpen && <button className="fixed inset-0 z-10 bg-[#172221]/25 lg:hidden" onClick={() => setMobileRailOpen(false)} aria-label="Close navigation overlay" />}
    <section className="flex min-w-0 flex-1 flex-col" id="top"><header className="flex h-[76px] items-center justify-between border-b border-[var(--line)] px-5 sm:px-8"><div className="flex items-center gap-3"><button className="rounded-lg p-2 text-xl hover:bg-[#edf1eb] lg:hidden" onClick={() => setMobileRailOpen(true)} aria-label="Open navigation">=</button><div><p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--ink-soft)]">Current focus</p><h1 className="mt-0.5 text-sm font-semibold sm:text-base">{activeTopic?.title ?? "New learning topic"}</h1></div></div><span className="hidden items-center gap-2 text-xs font-medium text-[var(--ink-soft)] sm:flex"><span className="h-2 w-2 rounded-full bg-[#53a982]" /> Backend connected</span></header>
      <div className="scrollbar-thin flex-1 overflow-y-auto"><div className="mx-auto max-w-[900px] px-5 pb-12 pt-9 sm:px-10 sm:pt-12"><div className="mb-10 flex items-end justify-between gap-6"><div><div className="mb-3 inline-flex items-center gap-2 rounded-full bg-[var(--sun-soft)] px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] text-[#8a5b1e]"><span className="h-1.5 w-1.5 rounded-full bg-[var(--sun)]" /> {question ? `Assessment - ${chat.questionIndex ?? 1} of ${chat.totalQuestions ?? 3}` : chat.phase}</div><h2 className="display-font max-w-xl text-[clamp(2.2rem,5vw,4rem)] leading-[0.98] tracking-[-0.045em]">Let&apos;s make this<br /><em className="text-[var(--teal)]">click.</em></h2></div></div>
        {error && <div role="alert" className="mb-6 rounded-xl border border-[#e7b7b0] bg-[#fff2ef] px-4 py-3 text-sm text-[#8a3c31]">{error}</div>}
        <div className="space-y-7">{displayMessages.map((item) => <MessageBubble key={item.id} message={item} />)}
          {chat.assistantDraft && <MessageBubble message={{ id: "draft", role: "assistant", content: chat.assistantDraft, phase: chat.phase, created_at: new Date().toISOString() }} draft />}
          {question && <section className="relative overflow-hidden rounded-[22px] border border-[#e7d6b7] bg-[#fffbf2] p-5 shadow-[0_12px_30px_rgba(122,88,36,0.06)] sm:p-7" aria-labelledby="question-title"><div className="relative"><div className="flex items-center justify-between gap-4"><span className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#a27332]">Question {chat.questionIndex ?? 1} <span className="mx-1">/</span> {chat.totalQuestions ?? 3}</span><span className="rounded-full border border-[#e8d3ac] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.1em] text-[#9c6c2a]">{question.difficulty}</span></div><h3 id="question-title" className="mt-5 max-w-2xl text-xl font-semibold leading-8 sm:text-2xl">{question.text}</h3><div className="mt-6 grid gap-2.5 sm:grid-cols-2">{(Object.entries(question.options) as [OptionLetter, string][]).map(([letter, label]) => <button key={letter} disabled={working} onClick={() => void handleAnswer(letter)} className={`group flex min-h-[58px] items-center gap-3 rounded-xl border px-3 text-left transition ${selectedOption === letter ? "border-[var(--teal)] bg-[var(--mint)]" : "border-[#eadfc9] bg-white hover:border-[#c4d5cb] hover:bg-[#f8fbf6]"}`} aria-pressed={selectedOption === letter}><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#f6f0e5] text-xs font-bold text-[#8f6a38]">{letter}</span><span className="text-sm font-medium text-[#34423f]">{label}</span></button>)}</div><p className="mt-5 text-xs text-[#927b59]">{working ? "Brainwise is preparing the next step..." : "Choose one answer to continue"}</p></div></section>}
          {activeTopic && !question && !messages.length && <div className="rounded-2xl border border-[var(--line)] bg-white p-6 text-sm text-[var(--ink-soft)]">Start this topic by sending your first question below.</div>}
        </div>
        <form onSubmit={handleSend} className="sticky bottom-0 mt-10 flex items-end gap-3 border-t border-[var(--line)] bg-white/95 py-4 backdrop-blur"><label htmlFor="follow-up" className="sr-only">Ask a follow-up question</label><textarea id="follow-up" disabled={working || chat.phase === "assessing"} value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder={chat.phase === "assessing" ? "Choose an answer above..." : "Ask a follow-up question..."} rows={1} className="max-h-32 min-h-[48px] flex-1 resize-none rounded-xl border border-[var(--line)] bg-[#f8faf7] px-4 py-3 text-sm outline-none transition placeholder:text-[#9aa59f] focus:border-[var(--teal)] focus:bg-white disabled:cursor-not-allowed disabled:opacity-60" /><button disabled={working || chat.phase === "assessing"} type="submit" className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-[var(--teal)] text-xl text-white transition hover:bg-[var(--teal-deep)] disabled:cursor-not-allowed disabled:opacity-40" aria-label="Send message">^</button></form>
      </div></div></section>
  </div></main>;
}

function parseQuestionMessage(content: string) {
  try {
    const parsed = JSON.parse(content) as { question_id?: string; difficulty?: string; text?: string; options?: Record<string, string>; thread_id?: string };
    if (parsed.question_id && parsed.difficulty && parsed.text && parsed.options && parsed.thread_id) return parsed;
  } catch {
    return null;
  }
  return null;
}

function MessageBubble({ message, draft = false }: { message: Message; draft?: boolean }) {
  const isUser = message.role === "user";
  return <article className={`flex gap-3 ${isUser ? "justify-end" : ""}`}><div className={`max-w-[80%] ${isUser ? "order-1" : ""}`}><div className={`rounded-2xl px-4 py-3.5 text-[15px] leading-7 ${isUser ? "rounded-br-md bg-[var(--teal)] text-white" : "rounded-bl-md bg-[#f0f3ee] text-[#34423f]"}`}>{message.content}{draft && <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-[var(--teal)] align-middle" />}</div><p className="mt-1.5 text-[10px] text-[var(--ink-soft)]">{isUser ? "You" : "Brainwise"}{draft ? " - streaming" : ""}</p></div>{!isUser && <span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-[var(--mint)] text-xs font-bold text-[var(--teal)]">B</span>}</article>;
}

function AuthScreen({ mode, setMode, onSubmit, error }: { mode: AuthMode; setMode: (mode: AuthMode) => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void; error: string }) {
  return <main className="grid min-h-screen place-items-center bg-[var(--background)] px-5 py-10"><section className="w-full max-w-[440px] rounded-[28px] border border-[var(--line)] bg-white p-7 shadow-[0_20px_60px_rgba(23,34,33,0.08)] sm:p-10"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--teal)] text-lg font-bold text-white">B</span><span className="display-font text-2xl font-semibold">brainwise</span></div><p className="mt-10 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--ink-soft)]">Your learning workspace</p><h1 className="display-font mt-3 text-4xl leading-none tracking-[-0.04em]">Learn with clarity.</h1><form onSubmit={onSubmit} className="mt-8 space-y-4">{mode === "register" && <label className="block text-sm font-semibold">Name<input required name="name" className="mt-2 w-full rounded-xl border border-[var(--line)] px-3 py-3 outline-none focus:border-[var(--teal)]" /></label>}<label className="block text-sm font-semibold">Email<input required type="email" name="email" className="mt-2 w-full rounded-xl border border-[var(--line)] px-3 py-3 outline-none focus:border-[var(--teal)]" /></label><label className="block text-sm font-semibold">Password<input required type="password" name="password" className="mt-2 w-full rounded-xl border border-[var(--line)] px-3 py-3 outline-none focus:border-[var(--teal)]" /></label>{error && <p role="alert" className="rounded-xl bg-[#fff2ef] px-3 py-2 text-sm text-[#8a3c31]">{error}</p>}<button className="w-full rounded-xl bg-[var(--teal)] px-4 py-3 font-bold text-white hover:bg-[var(--teal-deep)]">{mode === "login" ? "Sign in" : "Create account"}</button></form><button className="mt-5 w-full text-sm font-semibold text-[var(--teal)]" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "New to Brainwise? Create an account" : "Already have an account? Sign in"}</button></section></main>;
}