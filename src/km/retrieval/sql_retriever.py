import logging
import sqlite3

from pydantic import BaseModel

from km.domain.models import SqlResult
from km.llm import prompts
from km.llm.base import LLMClient
from km.retrieval.sql_guard import UnsafeSqlError, check_select_only
from km.storage.sql_store import SqlStore

log = logging.getLogger(__name__)


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
            return self._run(query.sql)
        except sqlite3.Error as e:
            # One self-correction attempt: show the model its query and the database error.
            # Unsafe SQL is never retried.
            log.warning("SQL failed (%s); asking for a corrected query", e)
            retry = (f"{question}\n\nYour previous query failed.\nQuery: {query.sql}\n"
                     f"Database error: {e}\nWrite a corrected query.")
            query = self._llm.structured(system, retry, _SqlQuery)
            try:
                return self._run(query.sql)
            except sqlite3.Error as e2:
                raise SqlRetrievalError(f"{e2} | SQL: {query.sql}") from e2

    def _run(self, raw_sql: str) -> SqlResult:
        try:
            sql = check_select_only(raw_sql)                         # layer 1: our own check
        except UnsafeSqlError as e:
            raise SqlRetrievalError(f"{e} | SQL: {raw_sql}") from e
        rows = self._store.query_read_only(sql, self._max_rows)      # layer 2: read-only DB
        return SqlResult(sql=sql, rows=rows)
