# KM Assistant

A small knowledge-management question-answering backend. It answers plain-English questions from
two kinds of company knowledge, decides by intent where to look, and checks every answer against
the evidence before showing it.

- **Unstructured:** PDF and Word policy documents, chunked and indexed in Chroma.
- **Structured:** SQLite tables (`employees`, `expenses`), queried by model-written, read-only SQL.
- **Routing:** each question goes to documents, SQL, or both (hybrid).
- **Groundedness:** a second LLM call checks the answer claim by claim. Unsupported claims are removed;
  if nothing is supported, the user gets "not enough evidence" instead of a guess.

## Architecture

```
question
  -> IntentRouter            (LLM, structured output: unstructured | structured | hybrid + reason)
  -> retrieval               (hybrid runs both in parallel threads)
       DocRetriever           Chroma top-4 chunks, each tagged with file + page
       SqlRetriever           LLM writes SELECT -> sql_guard (SELECT-only) -> read-only SQLite
  -> AnswerWriter            (LLM sees only the evidence; must cite [D1]/[SQL] after every fact,
                              or reply INSUFFICIENT_EVIDENCE)
  -> GroundednessValidator   (second LLM call: claim-by-claim verdict; label recomputed in code)
  -> QAService decides       grounded -> answer | partial -> supported claims only | else -> refusal
```

Layered `src/` layout. Dependencies point downward; only `llm/` knows an LLM vendor and only
`storage/` knows Chroma/SQLite.

```
src/km/
  config.py            Settings from .env (the token lives only here at runtime)
  container.py         composition root: builds every object from Settings
  observability.py     Langfuse tracing (on only when keys are set)
  domain/models.py     Route, DocChunk, SqlResult, Evidence, Verdict, AskResult
  llm/                 LLMClient interface, anthropic_client (production), grok_cli_client (local test double), prompts
  storage/             vector_store (Chroma), sql_store (SQLite, read-only queries)
  ingestion/           loaders (PDF pages, Word paragraphs + tables), chunker, indexer
  routing/ retrieval/ generation/ validation/
  services/qa_service.py   the pipeline and the final decision
  api/app.py           FastAPI: POST /ask, GET /health
  cli.py               km seed | ingest | ask | serve
tests/                 unit + integration tests (offline, FakeLLM) and eval/ (real LLM)
data/raw/docs/         4 test documents (fictional company); data/seed/seed.sql matching rows
```

## Key design decisions

| Decision | Why |
| --- | --- |
| SQLite + Chroma | Both run in-process: no database server to install on a company laptop. |
| One `LLMClient` interface | The company gateway (Anthropic SDK) and the local Grok CLI simulator are interchangeable via `KM_LLM_PROVIDER`; tests use a `FakeLLM`. |
| LLM-based routing with a reason | Handles varied phrasing; the reason makes each route explainable and debuggable. |
| Structured outputs for router, SQL writer and validator | No free-text parsing; responses are validated Pydantic objects. |
| Separate validator call, label recomputed in code | The checker is independent of the writer, and the verdict can never contradict its own claim list. |
| Two-layer SQL safety | `sql_guard` allows a single SELECT/WITH only, and the connection is opened `mode=ro`. |
| SQL writer must not encode policy | Thresholds live in the documents; the prompt forbids invented `CASE` flags (found during testing). |
| Word tables are extracted | The expense limits live in a Word table; a paragraphs-only loader silently missed them. |
| Langfuse behind one module | Tracing is optional, and `KM_TRACE_CONTENT=false` keeps prompts and document text out of traces. |

## How intent routing works

The router prompt describes both sources, including the live SQL schema, and asks for one label:

- **unstructured:** rules, processes, limits and definitions -> document search only.
- **structured:** counts, totals, lists and facts about specific employees or expenses -> SQL only.
- **hybrid:** needs both, typically a database fact compared with a policy rule
  ("Did Dana Kim's travel expense need VP approval?") -> both retrievers run in parallel.

## How groundedness works

1. The writer sees only tagged evidence (`[D1]`..`[D4]` chunks with file and page, `[SQL]` query and rows)
   and must cite a tag after every fact, or answer `INSUFFICIENT_EVIDENCE`.
2. The validator splits the answer into claims and marks each one supported only if the evidence
   states it explicitly (numbers and names must match; no outside knowledge).
3. Code recomputes the label: all supported -> `grounded`; some -> `partial` (only the supported
   claims are returned, with a note); none -> refusal.

When evidence is insufficient (no chunks and no SQL result, failed or unsafe SQL, the writer says so, or
nothing survives validation), the API returns `status: insufficient_evidence` and the message
"I could not find enough evidence in the documents or database to answer that."

## Run locally

Requires Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env      # then edit .env (see below)

km seed                          # create SQLite tables + demo rows
km ingest                        # index data/raw/docs (first run downloads an ~80 MB embedding model)
km ask "How many people work in Engineering?"
km serve                         # API at http://127.0.0.1:8000/docs
pytest                           # offline tests, no LLM needed
python tests/eval/run_eval.py    # 17-question evaluation against the configured LLM
```

### Environment variables (.env)

| Variable | Purpose |
| --- | --- |
| `KM_LLM_PROVIDER` | `anthropic` (company gateway) or `grok_cli` (local simulator) |
| `KM_LLM_API_TOKEN` | Your company LLM token (required for `anthropic`) |
| `KM_LLM_BASE_URL` | Company gateway URL; empty = api.anthropic.com |
| `KM_LLM_AUTH_MODE` | `api_key` (x-api-key header) or `bearer` |
| `KM_LLM_MODEL` | Default `claude-opus-5-5` |
| `KM_GROK_BIN`, `KM_GROK_MODEL`, `KM_GROK_EFFORT` | Grok CLI simulator settings (`KM_GROK_EFFORT=low` is much faster) |
| `HTTPS_PROXY`, `SSL_CERT_FILE` | Only if your network needs them; leave commented out otherwise |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | Optional tracing |
| `KM_TRACE_CONTENT` | `false` = traces carry timings, tokens and scores only |

### Local testing with the Grok CLI

Set `KM_LLM_PROVIDER=grok_cli` to simulate the company gateway with the locally installed, logged-in
`grok` CLI. Each LLM call runs `grok` headless, single-turn, with no tools, in an empty temp folder,
using `--json-schema` for structured outputs. It is slower than a direct API (several seconds per call)
and bills your Grok plan, but needs no company token.

### Example queries

```
km ask "What is the daily meal expense limit?"                        # unstructured
km ask "What is the total amount spent on travel?"                    # structured
km ask "Did Dana Kim's travel expense need VP approval?"              # hybrid
km ask "What is the CEO's salary?"                                    # insufficient evidence
```

## Evaluation results

`python tests/eval/run_eval.py` runs 17 questions from `tests/eval/questions.json` (8 document, 4 SQL,
3 hybrid, 2 not answerable). Run on 2026-11-23 with the Grok CLI simulator (`grok_cli`, effort `low`):

| Metric | Result |
| --- | --- |
| Route accuracy (answerable questions) | 15/15 |
| Expected status (grounded, or refused when unanswerable) | 17/17 |
| Answer contains the expected facts | 15/15 |
| Latency per question | median 20.0 s, max 48.1 s (CLI start-up per call dominates) |

Example hybrid answer (H1):

> Yes. Ben Ortiz has used more annual leave than his 2026 entitlement. On 1 January 2026 his length of
> service, measured from his hire date of 2023-07-15 [SQL], is ... less than 3 years. That gives 20 working
> days of annual leave [D1]. He has 0 carried-over days [SQL], so his allowance for the year is 20 days. He has
> used 22 days [SQL], which is 2 days over that entitlement. Leave beyond the entitlement is unpaid and needs
> HR Director approval as well as the line manager's [D3].

What the first run found, and the fixes:

| Issue | Fix |
| --- | --- |
| SQL writer encoded an invented approval threshold (`CASE WHEN amount_usd > 1000`) | Prompt forbids business rules in SQL |
| Validator rejected "Dana Kim submitted the expense" although her name is in the expense row | Validator prompt: values in one SQL row describe one record |
| Writer refused "Has Ben exceeded his leave?" because carry-over (up to 5 days) was unknown: a real data gap | Added `carried_over_days`; writer and validator get today's date and may do checked arithmetic and date calculations |

Grok is a simulator: re-run the eval against the company gateway (`KM_LLM_PROVIDER=anthropic`) before relying on these numbers.
