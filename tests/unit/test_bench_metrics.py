import json
from pathlib import Path

from km.bench import metrics as M
from km.bench.dataset import load_cases


def test_normalize_money_and_case():
    assert M.normalize("Total: $2,250.00 USD") == "total: 2250.00 usd"
    assert M.missing_facts("Ben Ortiz used $16,377.43", ["16377", "ben ortiz"]) == []
    assert M.missing_facts("It is 20 days", ["25"]) == ["25"]
    assert M.present_forbidden("There is NO LIMIT", ["no limit"]) == ["no limit"]


def test_rows_match_is_column_agnostic_and_order_insensitive():
    gold = [("Ana Lee",), ("Ben Ortiz",)]
    pred = [{"name": "Ben Ortiz", "amount": 95.5}, {"name": "Ana Lee", "amount": 1200}]
    assert M.rows_match(pred, gold)
    assert not M.rows_match(pred[:1], gold)                       # missing row
    assert not M.rows_match(pred + [{"name": "Chen Wu"}], gold)   # extra row


def test_rows_match_numbers_and_top_n():
    assert M.rows_match([{"avg": 190.12345}], [(190.12,)])
    ranked = [{"d": "Engineering", "t": 9}, {"d": "Sales", "t": 5}]
    assert M.rows_match(ranked, [("Engineering",)], ordered_prefix_ok=True)
    assert not M.rows_match(ranked, [("Sales",)], ordered_prefix_ok=True)


def test_reciprocal_rank_respects_location():
    got = [("a.pdf", "page 1"), ("b.pdf", "page 2"), ("a.pdf", "page 3")]
    assert M.reciprocal_rank(got, [("a.pdf", "page 3")]) == (3, 1 / 3)
    assert M.reciprocal_rank(got, [("b.pdf", None)]) == (2, 0.5)
    assert M.reciprocal_rank(got, [("c.docx", None)]) == (None, 0.0)


def test_wilson_interval_is_wide_for_small_samples():
    lo, hi = M.wilson(36, 40)
    assert 0.75 < lo < 0.8 and 0.95 < hi < 0.98


def test_v2_dataset_is_valid():
    path = Path("benchmarks/corpora/v2/dataset.jsonl")
    cases = load_cases(path)
    assert len(cases) == len({c.id for c in cases}) >= 40
    for c in cases:
        if c.expected_status == "grounded" and c.category not in ("adversarial",):
            assert c.must_include or c.reference_answer, c.id
    assert all(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())


def test_rows_contain_checks_fact_coverage_only():
    gold = [("Singapore", 70.0)]
    assert M.rows_contain([{"office": "Singapore", "amt": 70, "x": 1}, {"office": "London"}], gold)
    assert not M.rows_contain([{"name": "Marcus Tan", "amt": 70}], gold)   # office missing
