"""Measure search quality against a list of queries with known correct BLS codes."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from health_api.catalog.repository import FoodFilters, list_foods

DEFAULT_CASES = Path(__file__).resolve().parents[3] / "search_eval.tsv"
DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"


@dataclass(frozen=True)
class Case:
    query: str
    expected: frozenset[str]
    kind: str


@dataclass(frozen=True)
class Result:
    case: Case
    rank: int | None
    top: list[str]


def read_cases(path: Path = DEFAULT_CASES) -> list[Case]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        query, codes, kind = line.split("\t")
        cases.append(Case(query, frozenset(codes.split(",")), kind))
    return cases


def evaluate(connection: psycopg.Connection, cases: list[Case], depth: int = 5) -> list[Result]:
    results = []
    for case in cases:
        items = list_foods(connection, FoodFilters(q=case.query, limit=depth))["items"]
        codes = [(item["source"] or {}).get("external_id") for item in items]
        rank = next((i for i, code in enumerate(codes, 1) if code in case.expected), None)
        top = [f"{code} {item['name']}" for code, item in zip(codes, items, strict=True)]
        results.append(Result(case, rank, top))
    return results


def hit_rate(results: list[Result], within: int) -> float:
    return sum(r.rank is not None and r.rank <= within for r in results) / len(results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report food search top-1 and top-5 hit rates")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--verbose", action="store_true", help="show results for every query")
    options = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        results = evaluate(connection, read_cases(options.cases))
    for result in results:
        if options.verbose or result.rank != 1:
            print(f"{result.rank or '-':>2}  {result.case.query!r} ({result.case.kind})")
            for line in result.top[:3]:
                print(f"      {line}")
    print(f"top-1 {hit_rate(results, 1):.0%}  top-5 {hit_rate(results, 5):.0%}  n={len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
