import json
import re
from collections.abc import Iterator

from google import genai
from google.genai import errors, types

from institution_rag.config import (
    CHAT_MAX_OUTPUT_TOKENS,
    CHAT_MODEL,
    CHAT_MODEL_FALLBACK,
    CHAT_TEMPERATURE,
    HISTORY_LIMIT,
    RELEVANCE_DISTANCE,
    require_gemini_api_key,
)
from institution_rag.retriever import Source, retrieve

SYSTEM_INSTRUCTION = (
    "You are Muhammad Salman's friendly company assistant. "
    "Use the <context> to answer in your own words, like a natural conversation: "
    "paraphrase, summarize, and combine facts from different parts of it. "
    "Never copy sentences from the context word for word, and never mention "
    "chunks, sources, or that a context was given to you. "
    "Keep replies to 2-5 sentences unless the user asks for a list or details. "
    "Only when the context truly has no answer, reply: "
    "\"I'm sorry, that's not covered in the document.\""
)

REFUSAL_TEXT = (
    "I'm sorry, that's not covered in the document. "
    "Try asking about services, skills, pricing or contact details."
)

_SMALLTALK_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"^(hi+|hello|hey|yo|hiya|howdy|salam|assalam\w*)[!.?\s]*$", re.IGNORECASE
        ),
        "Hello! Ask me anything about Muhammad Salman's company document.",
    ),
    (
        re.compile(
            r"^(thanks|thank you|thx|ty|jazak\w*|appreciate it)[!.?\s]*$", re.IGNORECASE
        ),
        "You're welcome! Anything else about the document?",
    ),
    (
        re.compile(
            r"^(bye|goodbye|see you|good night|exit|quit)[!.?\s]*$", re.IGNORECASE
        ),
        "Goodbye! Come back anytime to ask about the document.",
    ),
    (
        re.compile(
            r"^(who are you|what are you|your name|what can you do)[?.\s]*$",
            re.IGNORECASE,
        ),
        (
            "I'm a test chatbot that answers only from Muhammad Salman's company "
            "document. Ask me about his services, skills, pricing or contact details."
        ),
    ),
]


def _event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _smalltalk_reply(message: str) -> str | None:
    if len(message) > 40:
        return None
    for pattern, reply in _SMALLTALK_RULES:
        if pattern.match(message):
            return reply
    return None


def _build_contents(
    messages: list[dict[str, str]], context: str, question: str
) -> list[types.Content]:
    contents = [
        types.Content(
            role="user" if message["role"] == "user" else "model",
            parts=[types.Part(text=message["content"])],
        )
        for message in messages
    ]
    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(f"<context>\n{context}\n</context>\n\nQuestion: {question}")
                )
            ],
        )
    )
    return contents


def _source_payload(sources: list[Source]) -> list[dict]:
    return [
        {
            "chunk_index": source.chunk_index,
            "score": source.score,
            "distance": source.distance,
            "filename": source.filename,
            "snippet": source.snippet,
        }
        for source in sources
    ]


def _open_stream(client: genai.Client, contents: list[types.Content]):
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=CHAT_TEMPERATURE,
        max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
    )
    last_error: errors.ServerError | None = None
    for model in (CHAT_MODEL, CHAT_MODEL_FALLBACK):
        try:
            return client.models.generate_content_stream(
                model=model, contents=contents, config=config
            )
        except errors.ServerError as exc:
            if "503" not in str(exc):
                raise
            last_error = exc
    raise last_error


def stream_reply(
    *, message: str, conversation_id: str, messages: list[dict[str, str]]
) -> Iterator[str]:
    yield _event("meta", {"conversation_id": conversation_id})

    refused = False
    assistant_text = ""
    try:
        canned = _smalltalk_reply(message)
        sources: list[Source] = []

        if canned is not None:
            yield _event("sources", {"sources": [], "smalltalk": True})
            assistant_text = canned
            yield _event("token", {"text": assistant_text})
        else:
            sources, best_distance = retrieve(message)
            yield _event(
                "sources",
                {"sources": _source_payload(sources), "smalltalk": False},
            )

            if not sources or best_distance > RELEVANCE_DISTANCE:
                refused = True
                assistant_text = REFUSAL_TEXT
                yield _event("token", {"text": assistant_text})
            else:
                context = "\n\n---\n\n".join(source.content for source in sources)
                client = genai.Client(api_key=require_gemini_api_key())
                stream = _open_stream(
                    client, _build_contents(messages, context, message)
                )
                for chunk in stream:
                    text = chunk.text
                    if text:
                        assistant_text += text
                        yield _event("token", {"text": text})

        messages.append({"role": "user", "content": message})
        messages.append({"role": "assistant", "content": assistant_text})
        if len(messages) > HISTORY_LIMIT:
            del messages[:-HISTORY_LIMIT]

        yield _event("done", {"conversation_id": conversation_id, "refused": refused})
    except Exception as exc:  # noqa: BLE001
        yield _event("error", {"detail": f"{type(exc).__name__}: {exc}"})
