"""The pipeline: route -> retrieve -> answer -> validate. Decides what the user sees."""
import contextvars
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from km.domain.models import AskResult, Evidence, Route, SqlResult
from km.generation.answer_writer import AnswerWriter
from km.llm.base import LLMError
from km.observability import score_trace, span  # Langfuse; no-ops when tracing is off
from km.retrieval.doc_retriever import DocRetriever
from km.retrieval.sql_retriever import SqlRetrievalError, SqlRetriever
from km.routing.intent_router import IntentRouter
from km.storage.sql_store import SqlStore
from km.validation.groundedness import GroundednessValidator

log = logging.getLogger(__name__)
NO_ANSWER = "I could not find enough evidence in the documents or database to answer that."


class QAService:
    def __init__(self, router: IntentRouter, docs: DocRetriever, sql: SqlRetriever,
                 writer: AnswerWriter, validator: GroundednessValidator, sql_store: SqlStore):
        self._router, self._docs, self._sql = router, docs, sql
        self._writer, self._validator, self._sql_store = writer, validator, sql_store

    def ask(self, question: str) -> AskResult:
        start = time.perf_counter()
        with span("qa.ask", question=question) as root:  # one Langfuse trace per question
            try:
                result = self._ask(question)
            except LLMError as e:
                log.error("LLM failure: %s", e)
                result = AskResult(question=question, status="error", answer=str(e))
            result.latency_ms = int((time.perf_counter() - start) * 1000)
            score_trace("status", result.status, "CATEGORICAL")
            root.update(output={"status": result.status, "answer": result.answer,
                                "sources": result.sources, "sql": result.sql})
        log.info("status=%s route=%s latency_ms=%d", result.status,
                 result.route.intent if result.route else None, result.latency_ms)
        return result

    def _ask(self, question: str) -> AskResult:
        with span("route") as s:
            route = self._router.route(question, self._sql_store.schema())
            s.update(output=route.model_dump())
        score_trace("route", route.intent, "CATEGORICAL")

        with span("retrieve", intent=route.intent) as s:
            evidence = self._retrieve(question, route)
            s.update(output={"doc_chunks": len(evidence.docs),
                             "sql": evidence.sql.sql if evidence.sql else None})
        base = dict(question=question, route=route,
                    sources=sorted({f"{d.source} ({d.location})" for d in evidence.docs}),
                    sql=evidence.sql.sql if evidence.sql else None)

        if evidence.is_empty():
            return AskResult(**base, status="insufficient_evidence", answer=NO_ANSWER)
        with span("write_answer") as s:
            answer = self._writer.write(question, evidence)
            s.update(output=answer)
        if answer is None:
            return AskResult(**base, status="insufficient_evidence", answer=NO_ANSWER)

        with span("validate") as s:
            verdict = self._validator.check(answer, evidence)
            s.update(output=verdict.model_dump())
        supported = sum(c.supported for c in verdict.claims)
        score_trace("groundedness", verdict.verdict, "CATEGORICAL")
        score_trace("supported_claim_ratio",
                    supported / len(verdict.claims) if verdict.claims else 0.0, "NUMERIC")

        if verdict.verdict == "grounded":
            return AskResult(**base, status="grounded", answer=answer, verdict=verdict)
        if verdict.verdict == "partially_grounded":
            kept = "\n".join(f"- {c.claim}" for c in verdict.claims if c.supported)
            return AskResult(**base, status="partial", verdict=verdict,
                             answer=f"{kept}\n(Unsupported statements were removed.)")
        return AskResult(**base, status="insufficient_evidence", answer=NO_ANSWER, verdict=verdict)

    def _retrieve(self, question: str, route: Route) -> Evidence:
        want_docs = route.intent in ("unstructured", "hybrid")
        want_sql = route.intent in ("structured", "hybrid")
        with ThreadPoolExecutor(max_workers=2) as pool:  # hybrid: both run in parallel
            # copy_context().run carries the current Langfuse trace into the worker thread
            docs_job = (pool.submit(contextvars.copy_context().run, self._docs.retrieve, question)
                        if want_docs else None)
            sql_job = (pool.submit(contextvars.copy_context().run, self._safe_sql, question)
                       if want_sql else None)
            docs = docs_job.result() if docs_job else []
            sql = sql_job.result() if sql_job else None
        return Evidence(docs=docs, sql=sql)

    def _safe_sql(self, question: str) -> SqlResult | None:
        try:
            return self._sql.retrieve(question)
        except SqlRetrievalError as e:  # bad SQL = no SQL evidence, not a crash
            log.warning("SQL retrieval failed: %s", e)
            return None
