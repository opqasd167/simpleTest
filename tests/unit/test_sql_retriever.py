from pathlib import Path

import pytest

from km.retrieval.sql_retriever import SqlRetrievalError, SqlRetriever
from km.storage.sql_store import SqlStore


class ScriptedLLM:
    """Returns the given SQL strings in order, one per call."""

    def __init__(self, *sqls):
        self.sqls, self.calls = list(sqls), 0

    def structured(self, system, user, schema):
        self.calls += 1
        return schema(sql=self.sqls.pop(0))


@pytest.fixture
def store(tmp_path):
    s = SqlStore(tmp_path / "km.db")
    s.init_from_script(Path("data/seed/seed.sql"))
    return s


def test_bad_column_is_corrected_once(store):
    llm = ScriptedLLM("SELECT amount FROM expenses", "SELECT SUM(amount_usd) AS total FROM expenses")
    result = SqlRetriever(llm, store, 50).retrieve("Total spend?")
    assert llm.calls == 2
    assert result.rows == [{"total": 2405.5}]


def test_gives_up_after_one_retry(store):
    llm = ScriptedLLM("SELECT nope FROM expenses", "SELECT still_nope FROM expenses")
    with pytest.raises(SqlRetrievalError):
        SqlRetriever(llm, store, 50).retrieve("Total spend?")


def test_unsafe_sql_is_not_retried(store):
    llm = ScriptedLLM("DELETE FROM expenses")
    with pytest.raises(SqlRetrievalError):
        SqlRetriever(llm, store, 50).retrieve("Delete all")
    assert llm.calls == 1
