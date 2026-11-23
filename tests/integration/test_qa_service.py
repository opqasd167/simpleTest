from pathlib import Path

from km.generation.answer_writer import AnswerWriter
from km.retrieval.sql_retriever import SqlRetriever
from km.routing.intent_router import IntentRouter
from km.services.qa_service import QAService
from km.storage.sql_store import SqlStore
from km.validation.groundedness import GroundednessValidator


class NoDocs:
    def retrieve(self, question):
        return []


def make_service(tmp_path, llm):
    store = SqlStore(tmp_path / "km.db")
    store.init_from_script(Path("data/seed/seed.sql"))
    return QAService(IntentRouter(llm), NoDocs(), SqlRetriever(llm, store, 50),
                     AnswerWriter(llm), GroundednessValidator(llm), store)


def test_grounded_answer_is_returned(tmp_path, make_llm):
    result = make_service(tmp_path, make_llm()).ask("How many employees?")
    assert result.status == "grounded"
    assert result.sql == "SELECT COUNT(*) AS n FROM employees"


def test_unsupported_answer_is_replaced(tmp_path, make_llm):
    result = make_service(tmp_path, make_llm(supported=False)).ask("How many employees?")
    assert result.status == "insufficient_evidence"


def test_unsafe_sql_never_runs(tmp_path, make_llm):
    llm = make_llm(sql="DELETE FROM employees")
    service = make_service(tmp_path, llm)
    result = service.ask("Delete everyone")
    assert result.status == "insufficient_evidence"          # no SQL evidence, no answer
    rows = SqlStore(tmp_path / "km.db").query_read_only("SELECT COUNT(*) AS n FROM employees", 1)
    assert rows == [{"n": 4}]                                # data untouched


def test_model_says_insufficient(tmp_path, make_llm):
    result = make_service(tmp_path, make_llm(answer="INSUFFICIENT_EVIDENCE")).ask("CEO salary?")
    assert result.status == "insufficient_evidence"
