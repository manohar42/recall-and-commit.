# Recall & Commit (AI edition)

Evidence-backed memory for your conversations, built with **FastAPI + React**, and an AI layer built on
**LangChain + LangGraph + Google Gemini**.

| Feature | What the AI does | Where |
|---|---|---|
| 1. Commitments | Gemini reads **each conversation** and decides, line by line, whether you made a real commitment (vs. a hedge, a question, or someone else's promise). Only AI-approved candidates reach the Review inbox, each with a label, confidence, explanation and extracted dates. You still approve or reject. | Review inbox, Conversations |
| 2. Recall | Finds the relevant transcript excerpts, then Gemini writes a **paragraph answer** with numbered citations `[1]`. Every citation has a **View conversation** button that opens the full transcript with the lines highlighted. | Recall, Assistant |
| 3. What If | Checks a proposed task against your ledger (overlaps, tight gaps, dependencies, missing info) and Gemini writes a **paragraph** explaining the tasks involved, any conflicts and other issues. Nothing changes until you prepare and confirm. | What If |

Without a key the app still works end to end using a built-in rules fallback, and the UI says so clearly.

## Quick start (Windows CMD, Docker Desktop)

```cmd
cd C:\Users\manoh\Projects\recall-commit-ai
copy .env.example .env
notepad .env
```
Put your key on the `GOOGLE_API_KEY=` line (free key: https://aistudio.google.com/apikey) and save.

```cmd
docker compose down -v
docker compose build --no-cache
docker compose up -d
docker compose ps
```
`down -v` removes the old database volume from the previous version. Only needed once.

Open **http://localhost:5173**. Then load the sample month, either:
- in the UI: Review inbox > **Import sample month** > **Analyze with Gemini**, or
- from CMD:
  ```cmd
  docker compose exec api python -m scripts.seed_demo --analyze
  ```

Expected output:
```
Loaded 61 conversations from /app/sample_data/conversations.json
Imported: 61 created, 0 updated, 0 unchanged, 353 utterances, ... recall excerpts indexed.
Ledger: 20 pre-approved commitments (11 done, 9 open).
  AI review (gemini): analyzed 10, failed 0, remaining 51, new candidates ...
...
```

Check the AI connection any time: http://localhost:8000/api/ai/status (`"configured": true, "mode": "gemini"`).
API docs: http://localhost:8000/docs

## Things to try with the sample data

- Recall: "Which laptop did Maya choose and why?", "What did we decide about the lease?", "What did I promise Mom about the holidays?"
- What If: the default form (decorating Lucia's on Sat Oct 24, 4:45-6:15 PM) collides with the cake pickup and is tight before the birthday dinner.
- Review inbox: approve, edit then approve, reject, or open the source conversation.
- Assistant: "What did I agree to for Saturday?"

## Sample data

`backend/sample_data/conversations.json` has 61 fictional conversations from Oct 1-31 2026 (Alex is the user),
in the same import format the app uses:

```json
{"schema_version": "1.0", "source": "sample", "conversations": [
  {"external_id": "...", "title": "...", "started_at": "2026-10-02T12:15:00-07:00", "participants": ["Alex", "Maya"],
   "user_speaker": "Alex", "utterances": [{"sequence": 1, "speaker": "Maya", "occurred_at": "...", "text": "..."}]}]}
```
Optional `seed_commitments` entries are used only by `seed_demo` to pre-fill the ledger. The importer also accepts a
plain list of conversations and the old `external/day/hour/people/lines` format. You can upload any of these in the
UI with **Upload JSON** (no 100-conversation limit).

To edit the conversations, change the readable files in `backend/sample_data/source/` and run
`python sample_data/source/build_sample.py` from `backend`.

Seed options: `--file path.json`, `--keep-existing` (do not wipe first), `--no-ledger`, `--analyze`.

## How the AI is wired

```
backend/app/ai/
  llm.py               ChatGoogleGenerativeAI via LangChain, structured output, readable errors
  schemas.py           Pydantic schemas Gemini must return
  commitment_graph.py  LangGraph: prepare -> gemini_review | rules_review -> validate
  recall_graph.py      LangGraph: retrieve (SQLite FTS5) -> gemini_answer | extractive | no_evidence -> validate citations
  whatif_graph.py      LangGraph: gather ledger context -> gemini_explain | rules_explain
  fallback_rules.py    used when no key is set or Gemini fails
```
Safety rules enforced in code, not just in prompts: only the user's own lines can become candidates, transcript text is
treated as untrusted data (the sample includes a prompt-injection voicemail), citations must point to real evidence,
and the ledger only changes through approve or prepare + confirm. If you add a key after a rules-only run, the next
Analyze re-reviews those conversations with Gemini and replaces the rules suggestions you have not acted on.

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `GOOGLE_API_KEY` | empty | also accepts `GEMINI_API_KEY` |
| `GEMINI_MODEL` | `gemini-3.8-flash` | any Gemini model id your key can use |
| `API_PORT` / `WEB_PORT` | 8000 / 5173 | change if a port is busy |

After editing `.env`: `docker compose up -d --force-recreate api`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Banner "Gemini not configured" | `.env` must be next to `docker-compose.yml`, line `GOOGLE_API_KEY=...` without quotes, then `docker compose up -d --force-recreate api` |
| "Gemini rejected the API key" | Regenerate the key in AI Studio |
| "rate limit or quota reached" | Free tier limits; wait a minute and click Analyze again (it continues where it stopped) |
| "model ... was not found" | Set `GEMINI_MODEL` to a model listed for your key |
| `port is already allocated` | Set `API_PORT=8001` or `WEB_PORT=5174` in `.env` |
| Old data or old errors after updating | `docker compose down -v` then `docker compose build --no-cache` then `docker compose up -d` |
| Seed says file not found | The file must be `backend\sample_data\conversations.json` (folder name exactly `sample_data`) |
| Logs | `docker compose logs -f api` |

## Local development (without Docker)

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.seed_demo
uvicorn app.main:app --reload
```
In a second window: `cd frontend`, `npm ci`, `npm run dev`, then open http://localhost:5173 (Vite forwards `/api` to port 8000).

Tests: `cd backend && pytest -q` (Gemini is simulated in tests, no key needed). Lint: `ruff check app tests scripts`, `npm run lint`.
