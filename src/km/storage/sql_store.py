import sqlite3
from contextlib import closing
from pathlib import Path


class SqlStore:
    """The only code that touches SQLite. Model-written SQL always runs read-only."""

    def __init__(self, path: Path):
        self._path = path

    def init_from_script(self, script: Path) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._path)) as con:
            con.executescript(script.read_text(encoding="utf-8"))
            con.commit()

    def schema(self) -> str:
        with closing(self._read_only()) as con:
            rows = con.execute("SELECT sql FROM sqlite_master "
                               "WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        return "\n".join(r[0] for r in rows)

    def query_read_only(self, sql: str, max_rows: int) -> list[dict]:
        with closing(self._read_only()) as con:
            cur = con.execute(sql)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchmany(max_rows)]

    def _read_only(self) -> sqlite3.Connection:
        # mode=ro: SQLite itself refuses INSERT, UPDATE, DELETE and DROP
        return sqlite3.connect(f"{self._path.resolve().as_uri()}?mode=ro", uri=True)
