import pytest

from km.retrieval.sql_guard import UnsafeSqlError, check_select_only


def test_allows_select():
    assert check_select_only("SELECT * FROM employees;") == "SELECT * FROM employees"


def test_allows_column_names_containing_keywords():
    assert check_select_only("SELECT created_at, last_update FROM t")


@pytest.mark.parametrize("sql", [
    "DELETE FROM employees",
    "SELECT 1; DROP TABLE employees",
    "PRAGMA table_info(employees)",
    "WITH x AS (SELECT 1) DELETE FROM employees",
])
def test_blocks_unsafe(sql):
    with pytest.raises(UnsafeSqlError):
        check_select_only(sql)
