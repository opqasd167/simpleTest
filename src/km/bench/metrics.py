"""Pure scoring functions: no LLM, no I/O. Unit-tested in tests/unit/test_bench_metrics.py."""
import math
import re
import statistics

SCORING_VERSION = "2"  # bump whenever scoring rules change; compare() warns across versions
_NUM_SEP = re.compile(r"(?<=\d),(?=\d)")


def normalize(text: str) -> str:
    """Lower-case, drop thousands separators, '$' and repeated spaces: '$2,250.00' -> '2250.00'."""
    text = _NUM_SEP.sub("", text.lower()).replace("$", "")
    return " ".join(text.split())


def missing_facts(answer: str, facts: list[str]) -> list[str]:
    a = normalize(answer)
    return [f for f in facts if normalize(f) not in a]


def present_forbidden(answer: str, forbidden: list[str]) -> list[str]:
    a = normalize(answer)
    return [f for f in forbidden if normalize(f) in a]


def _cell(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return f"{round(float(v), 2):.2f}"
    s = str(v).strip().lower()
    try:
        return f"{round(float(s), 2):.2f}"
    except ValueError:
        return s


def rows_match(pred: list[dict], gold: list[tuple], ordered_prefix_ok: bool = False) -> bool:
    """Execution accuracy, column-agnostic.

    Every gold row's values must appear inside a distinct predicted row (extra predicted columns are fine).
    Row counts must be equal, unless the gold query is a top-N query (LIMIT): then a longer predicted result
    passes if its first rows match the gold rows in order."""
    p = [{_cell(v) for v in r.values()} for r in pred]
    g = [{_cell(v) for v in r} for r in gold]
    if len(p) == len(g):
        used: set[int] = set()
        for gs in g:
            hit = next((i for i, ps in enumerate(p) if i not in used and gs <= ps), None)
            if hit is None:
                return False
            used.add(hit)
        return True
    if ordered_prefix_ok and len(p) > len(g):
        return all(gs <= ps for gs, ps in zip(g, p))
    return False


def rows_contain(pred: list[dict], gold: list[tuple]) -> bool:
    """Fact coverage for hybrid questions: every gold row's values appear in SOME predicted row.

    Hybrid SQL should fetch the facts a policy check needs (it must not apply policy thresholds itself),
    so extra rows and a different row shape are fine; missing facts are not."""
    p = [{_cell(v) for v in r.values()} for r in pred]
    return all(any({_cell(v) for v in g} <= ps for ps in p) for g in gold)


def reciprocal_rank(retrieved: list[tuple[str, str]], gold: list[tuple[str, str | None]]) -> tuple[int | None, float]:
    """(1-based rank of the first chunk matching any gold source, reciprocal rank)."""
    for i, (src, loc) in enumerate(retrieved, 1):
        if any(src == gs and (gl is None or loc == gl) for gs, gl in gold):
            return i, 1.0 / i
    return None, 0.0


def wilson(passed: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a pass rate. With 40 cases, 90% really means roughly 77-96%."""
    if n == 0:
        return (0.0, 0.0)
    p = passed / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[pct - 1]


def rate_block(passed: list[bool]) -> dict:
    n, k = len(passed), sum(passed)
    lo, hi = wilson(k, n)
    return {"n": n, "passed": k, "rate": round(k / n, 3) if n else 0.0, "ci95": [round(lo, 3), round(hi, 3)]}
