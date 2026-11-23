import sqlite3

from pydantic import BaseModel

from km.domain.models import SqlResult
from km.llm import prompts
from km.llm.base import LLMClient
from km.retrieval.sql_guard import UnsafeSqlError, check_select_only
from km.storage.sql_store import SqlStore


class SqlRetrievalError(Exception):
    """The generated SQL was unsafe or failed to run."""


class _SqlQuery(BaseModel):
    sql: str


class SqlRetriever:
    def __init__(self, llm: LLMClient, store: SqlStore, max_rows: int):
        self._llm, self._store, self._max_rows = llm, store, max_rows

    def retrieve(self, question: str) -> SqlResult:
        system = prompts.SQL_WRITER.format(schema=self._store.schema())
        query = self._llm.structured(system, question, _SqlQuery)
        try:
            sql = check_select_only(query.sql)                       # layer 1: our own check
            rows = self._store.query_read_only(sql, self._max_rows)  # layer 2: read-only DB
        except (UnsafeSqlError, sqlite3.Error) as e:
            raise SqlRetrievalError(f"{e} | SQL: {query.sql}") from e
        return SqlResult(sql=sql, rows=rows)
