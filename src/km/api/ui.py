"""Gradio chat UI for trying the assistant in a browser.

Mounted at /ui by api/app.py when the optional `ui` extra is installed (pip install -e ".[ui]").
It calls QAService in-process, logs questions with channel="ui", and thumbs up/down go to the same
feedback log as POST /feedback, so `python -m km.bench harvest` picks them up.
"""
import json
import re
from collections.abc import Callable

import gradio as gr

from km.config import Settings
from km.domain.models import AskResult
from km.question_log import log_feedback, log_question
from km.services.qa_service import QAService

EXAMPLES = [
    "What is the daily meal expense limit?",
    "What is the total amount spent on travel?",
    "Did Dana Kim's travel expense need VP approval?",
    "How many people work in Engineering?",
    "What is the CEO's salary?",
]
STATUS = {
    "grounded": "✅ Grounded",
    "partial": "🟡 Partially grounded (unsupported statements removed)",
    "insufficient_evidence": "⚪ Not enough evidence",
    "error": "❌ Error",
}
EMPTY_DETAILS = "Ask a question to see how it was routed, the evidence used and the claim check."
_TAG = re.compile(r"\[(D\d+|SQL)\]")


def _text(content) -> str:
    """Chat message content as plain text (Gradio may hand it back as a list of content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(_text(c) for c in content)
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    return str(content or "")


def _question_before(history: list, index) -> str | None:
    """The user question that a liked/disliked assistant message (at `index`) answered."""
    i = index if isinstance(index, int) else index[0]
    return next((_text(m["content"]) for m in reversed(history[:i]) if m["role"] == "user"), None)


def _answer_md(r: AskResult) -> str:
    answer = _TAG.sub(r"**[\1]**", r.answer)
    return f"{answer}\n\n<sub>{STATUS.get(r.status, r.status)} · {r.latency_ms / 1000:.1f} s</sub>"


def _details_md(r: AskResult) -> str:
    lines = [f"### {STATUS.get(r.status, r.status)}", f"**Latency:** {r.latency_ms / 1000:.1f} s"]
    if r.route:
        lines.append(f"**Route:** `{r.route.intent}` — {r.route.reason}")
    if r.verdict and r.verdict.claims:
        lines += ["", "#### Claim check", "| | Claim | Evidence |", "|---|---|---|"]
        for c in r.verdict.claims:
            claim = c.claim.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {'✅' if c.supported else '❌'} | {claim} | {c.evidence_tag} |")
    if r.evidence:
        lines += ["", "#### Evidence"]
        for e in r.evidence:
            if e.tag == "SQL":
                lines += [f"**[SQL]**", f"```sql\n{e.label}\n```", _rows_md(e.text)]
            else:
                body = e.text.strip().replace("\n", "\n> ")
                lines += [f"<details><summary><b>[{e.tag}]</b> {e.label}</summary>\n\n> {body}\n\n</details>"]
    elif r.sql:
        lines += ["", "#### SQL", f"```sql\n{r.sql}\n```"]
    return "\n".join(lines)


def _rows_md(rows_json: str, limit: int = 20) -> str:
    rows = json.loads(rows_json)
    if not rows:
        return "_No rows returned._"
    cols = list(rows[0])
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(row.get(c, "")).replace("|", "\\|") for c in cols) + " |" for row in rows[:limit]]
    if len(rows) > limit:
        out.append(f"\n_{len(rows) - limit} more rows not shown._")
    return "\n".join(out)


def build_ui(get_service: Callable[[], QAService], get_settings: Callable[[], Settings]) -> gr.Blocks:
    def add_question(question: str, history: list):
        question = (question or "").strip()
        if len(question) < 3:
            gr.Warning("Please type a question of at least 3 characters.")
            return question, history, ""
        return "", history + [{"role": "user", "content": question}], question

    def answer(question: str, history: list):
        if not question:
            return history, gr.update()
        try:
            result = get_service().ask(question)
        except Exception as e:  # e.g. missing token or index: show it instead of a blank error toast
            return history + [{"role": "assistant", "content": f"❌ {type(e).__name__}: {e}"}], gr.update()
        log_question(get_settings().question_log, result, channel="ui")
        return history + [{"role": "assistant", "content": _answer_md(result)}], _details_md(result)

    def on_feedback(evt: gr.LikeData, history: list):
        if evt is None or evt.liked is None:
            return
        question = _question_before(history, evt.index)
        if question:
            log_feedback(get_settings().question_log, question, bool(evt.liked))
            gr.Info("Thanks, feedback recorded.")

    with gr.Blocks(title="KM Assistant") as ui:
        gr.Markdown("# KM Assistant\nAsk about company policies (documents) or employees and expenses "
                    "(database). Every answer is checked against the evidence before it is shown.")
        pending = gr.State("")
        with gr.Row():
            with gr.Column(scale=3):
                chat = gr.Chatbot(height=520, label="Conversation", buttons=["copy"],
                                  placeholder="Pick an example below or type your own question.")
                with gr.Row():
                    box = gr.Textbox(placeholder="Ask a question…", show_label=False, scale=5, autofocus=True)
                    send = gr.Button("Ask", variant="primary", scale=1)
                gr.Examples(EXAMPLES, inputs=box, label="Examples")
                clear = gr.Button("Clear conversation", size="sm")
            with gr.Column(scale=2):
                details = gr.Markdown(EMPTY_DETAILS, label="Details", container=True)

        for trigger in (box.submit, send.click):
            trigger(add_question, [box, chat], [box, chat, pending], queue=False).then(
                answer, [pending, chat], [chat, details])
        chat.like(on_feedback, [chat], None)
        clear.click(lambda: ([], EMPTY_DETAILS), None, [chat, details], queue=False)
    return ui
