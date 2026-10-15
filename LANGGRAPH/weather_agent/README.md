# Weather Places Agent

FastAPI chat endpoint + LangGraph workflow: the user writes a temperature in natural
language, the graph finds countries/cities at that temperature via web search, then a
websearch agent picks the best places there.

## Setup

```bash
uv sync
```

`.env` (gitignored) must contain:

```
openai_api_key=sk-...
tavily_api_key=tvly-...
```

## Run

```bash
uv run uvicorn weather_agent.main:app --reload
```

- `GET /health` → `{"status": "ok"}`
- `POST /chat` with `{"message": "I want 25 degrees"}`

## Graph

```
START → extract_temperature ─┬─(temp given)→ search_exact ─┬─(match)→ best_places → format_answer → END
                             │                             └─(none) → search_closest ─┤
                             └─(no temp) → direct_reply → END                         └─(none) → direct_reply
```

- `search_exact`: websearch agent verifies places at exactly the target °C.
- `search_closest`: fallback for places within ±3°C (flagged `fallback_used`).
- `best_places`: websearch agent ranks the top places to visit there.

## Response

```json
{
  "reply": "...",
  "temperature": 25,
  "exact_match": true,
  "fallback_used": false,
  "candidates": [{"country": "Spain", "city": "Seville", "temperature_c": 25}]
}
```
