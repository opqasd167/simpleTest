# KM Assistant

Answers questions from policy documents and a SQL database, checking every claim against evidence. Details: [guideline.md](guideline.md).

## Setup

1. Run `setup.cmd` (Windows) or `./setup.sh`.
2. Add LLM settings to `.env`.
3. `km seed` (demo database)
4. `km ingest` (index documents)
5. `km serve`
6. Visit http://127.0.0.1:8000/ui

## Five test cases

`pytest tests/integration/test_five_questions.py -v -s`

1. Meal limit? Documents only.
2. Total travel spend? SQL only.
3. Dana Kim's VP approval? SQL first, then documents.
4. Ben Ortiz's leave? Unsupported claim removed.
5. CEO's salary? Refuses, never guesses.
