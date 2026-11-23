# Setup guide

On Windows, double-click **`setup.cmd`**. On macOS or Linux, run `./setup.sh`.

## What it does, in order

1. **Finds Python 3.11 or newer.** If none is installed, it offers to install it with winget.
2. **Creates `.venv`, or reuses the existing one**, then installs the project with the same extras CI
   uses (`dev,ocr,multilingual,ui`). On later runs it skips the install unless `pyproject.toml` has
   changed.
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
   the chat UI at `http://127.0.0.1:8000/ui`. If a server is already running on port 8000, it just
   opens the browser.

When you double-click it, the window stays open at the end so you can read the results. You can run it
as many times as you like. Later runs are faster because the install and model downloads are skipped;
most of the time goes to indexing, the tests and the benchmark.

## Options

| Option | Effect |
| --- | --- |
| `--yes` | Never asks anything and keeps `.env` as it is |
| `--offline` | Skips the live LLM question |
| `--no-bench` | Skips the retrieval benchmark |
| `--reinstall` | Runs `pip install` even when `pyproject.toml` is unchanged |

Example: `setup.cmd --yes --offline`

## If a step fails

The summary names the failed step. Scroll up to see its error, fix it, and run the script again. Steps
that already finished are quick the second time.

**"km.exe is in use" (Windows):** a `km serve` or `km ask` is still running, and Windows will not let
pip replace a running program. Stop it with Ctrl+C in its window, then run setup again.
