# KM Assistant

Answers questions from policy documents and a SQL database, checking every claim against evidence. Details: [guideline.md](guideline.md).

## Architecture

1. **Ingest:** PDF/Word files are chunked and indexed in Chroma; demo tables go into SQLite.
2. **Route:** an LLM labels the question unstructured, structured or hybrid.
3. **Retrieve:** document search, model-written SQL, or both.
4. **Answer:** the LLM sees only the evidence and cites `[D1]`/`[SQL]` after every fact.
5. **Validate:** a second LLM call checks each claim.

## Key design decisions

- **SQLite + Chroma:** both run in-process, so there's no server to install.
- **Structured outputs:** the router, SQL writer and validator return validated Pydantic objects.
- **Read-only SQL:** single `SELECT` only, on a `mode=ro` connection.

## Intent routing

The router prompt includes the live database schema.

- **Unstructured:** rules and limits → document search.
- **Structured:** counts, totals and facts about employees or expenses → SQL.
- **Hybrid:** a database fact checked against a policy → SQL first; its office and date steer document search.

## Groundedness

The validator marks each claim supported or not, and code sets the result:

- All supported → answer.
- Some → only the supported claims.
- None, or no evidence → "I could not find enough evidence…"

## Setup

1. Run `setup.cmd` (Windows) or `./setup.sh`.
2. Add LLM settings to `.env`: `KM_LLM_PROVIDER` (`anthropic`, `gateway` or `grok_cli`), plus its token and URL.
3. `km seed` (demo database)
4. `km ingest` (index documents)
5. `km serve`
6. Visit http://127.0.0.1:8000/ui

## Five test cases

Each one is also an example query: `km ask "What is the daily meal expense limit?"`

`pytest tests/integration/test_five_questions.py -v -s`

1. Meal limit? Documents only.
2. Total travel spend? SQL only.
3. Dana Kim's VP approval? SQL first, then documents.
4. Ben Ortiz's leave? Unsupported claim removed.
5. CEO's salary? Refuses, never guesses.
