import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum)\b", re.IGNORECASE)


class UnsafeSqlError(ValueError):
    pass


def check_select_only(sql: str) -> str:
    """Layer 1 of SQL safety (layer 2 is the read-only connection)."""
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        raise UnsafeSqlError("Only one statement is allowed")
    if not cleaned.lower().startswith(("select", "with")):
        raise UnsafeSqlError("Only SELECT queries are allowed")
    if FORBIDDEN.search(cleaned):
        raise UnsafeSqlError("Query contains a forbidden keyword")
    return cleaned
