# Setup guide

On Windows, double-click **`setup.cmd`**. On macOS or Linux, run `./setup.sh`.

## What it does, in order

1. **Finds Python 3.11 or newer.** If none is installed, it offers to install it with winget.
2. **Creates `.venv`, or reuses the existing one**, then installs the project with the same extras CI
   uses (`dev,ocr,multilingual`).
3. **Sets up `.env`.** If there isn't one, it copies `.env.example` and asks once how to reach an LLM:
   - your company token (typed in hidden)
   - the Grok CLI, which it picks by default when `grok` is installed
   - skip, and run only the offline steps

   An existing `.env` is never overwritten.
4. **Runs `km seed` and `km ingest`.** The first run downloads the embedding and OCR models, which can
   take a few minutes.
5. **Runs `pytest`.** These tests are offline and make no LLM calls.
6. **Runs the free retrieval benchmark.** It makes no LLM calls and fails if the pass rate is below 0.9.
   The report is saved in `benchmarks/runs/`.
7. **Asks one live question**, "How many people work in Engineering?", but only when an LLM is
   configured.
8. **Prints a summary** of each step (OK, WARN, FAIL or SKIP) and offers to start the API and open
   `http://127.0.0.1:8000/docs`.

When you double-click it, the window stays open at the end so you can read the results. You can run it
as many times as you like; a second run takes about 20 seconds.

## Options

| Option | Effect |
| --- | --- |
| `--yes` | Never asks anything and keeps `.env` as it is |
| `--offline` | Skips the live LLM question |
| `--no-bench` | Skips the retrieval benchmark |

Example: `setup.cmd --yes --offline`

## If a step fails

The summary names the failed step. Scroll up to see its error, fix it, and run the script again. Steps
that already finished are quick the second time.
