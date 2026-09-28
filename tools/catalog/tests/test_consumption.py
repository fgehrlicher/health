import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from health_catalog.consumption import ItemInput, day_bounds, status, summarize
from pydantic import ValidationError
from test_api import request
from test_registration import QUARK, request_json


@pytest.mark.parametrize(
    "item",
    [
        {"food": "x"},
        {"food": "x", "amount": 1, "portion": "Becher"},
        {"food": "x", "amount_min": 1},
        {"food": "x", "amount_min": 2, "amount_max": 1},
        {"food": "x", "amount": 0},
        {"food": "x", "amount": 100, "energy_kcal": 500},
    ],
)
def test_items_need_exactly_one_amount_and_no_nutrition(item):
    with pytest.raises(ValidationError):
        ItemInput.model_validate(item)


def item(amount_min, amount_max, **nutrition):
    return {
        "amount_min": Decimal(amount_min),
        "amount_max": Decimal(amount_max),
        "reference_quantity": Decimal(100),
        "nutrition": {key: str(value) for key, value in nutrition.items()},
    }


def test_status_and_totals_come_from_amounts_and_catalog_values():
    exact = item(400, 400, energy_kcal=68, protein_g="12.4")
    ranged = item(100, 130, energy_kcal=250)
    assert status([]) == "unknown"
    assert status([exact]) == "measured"
    assert status([exact, ranged]) == "estimated"
    totals = summarize([exact, ranged])
    assert totals["energy_kcal"] == {"min": "522", "max": "597", "items_without_value": 0}
    assert totals["protein_g"] == {"min": "49.60", "max": "49.60", "items_without_value": 1}


def test_days_follow_local_midnight_across_dst(monkeypatch):
    monkeypatch.setenv("HEALTH_TIMEZONE", "Europe/Berlin")
    start, end = day_bounds(date(2026, 10, 25))  # clocks go back: a 25-hour day
    assert start.utcoffset() == timedelta(hours=2) and end.utcoffset() == timedelta(hours=1)
    # Same-zone subtraction in Python is wall-clock; compare absolute times.
    assert end.astimezone(UTC) - start.astimezone(UTC) == timedelta(hours=25)


def test_log_a_day_against_postgres(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("HEALTH_TIMEZONE", "Europe/Berlin")
    barcode = "4000000000013"  # valid check digit, not a real product
    day = "2026-01-15"
    created_ids = []
    try:
        food = request_json(
            "POST", "/api/foods", QUARK | {"name": "Log test quark", "barcode": barcode}
        ).json()["food"]

        dry = request_json(
            "POST",
            "/api/log/entries?dry_run=true",
            {
                "observation": "whole cup",
                "eaten_at": f"{day}T08:00:00",
                "items": [
                    {"food": food["slug"], "portion": "Becher"},
                ],
            },
        )
        assert dry.status_code == 200
        assert dry.json()["totals"]["protein_g"]["min"] == "49.60"
        assert request(f"/api/log/days/{day}").json()["entries"] == []

        measured = request_json(
            "POST",
            "/api/log/entries",
            {
                "observation": "whole cup",
                "eaten_at": f"{day}T08:00:00",
                "items": [
                    {"food": food["slug"], "portion": "Becher"},
                ],
            },
        )
        assert measured.status_code == 201, measured.text
        created_ids.append(measured.json()["id"])
        assert measured.json()["status"] == "measured"
        assert measured.json()["items"][0]["amount_min"] == "400"
        assert measured.json()["totals"]["energy_kcal"]["min"] == "272"

        estimated = request_json(
            "POST",
            "/api/log/entries",
            {
                "observation": "rice with broccoli",
                "eaten_at": f"{day}T13:00:00+01:00",
                "items": [
                    {"food": "bls4-c352032", "label": "Reis", "amount_min": 150, "amount_max": 250},
                    {"food": "bls4-g312132", "amount": 100},
                ],
            },
        )
        assert estimated.status_code == 201, estimated.text
        created_ids.append(estimated.json()["id"])
        assert estimated.json()["status"] == "estimated"

        unknown = request_json(
            "POST",
            "/api/log/entries",
            {"observation": "dinner at the Italian place", "eaten_at": f"{day}T20:00:00"},
        )
        created_ids.append(unknown.json()["id"])
        assert unknown.json()["status"] == "unknown"

        summary = request(f"/api/log/days/{day}").json()
        assert summary["counts"] == {"measured": 1, "estimated": 1, "unknown": 1}
        kcal = summary["totals"]["energy_kcal"]
        assert kcal["measured"] == "272"
        assert Decimal(kcal["estimated_min"]) < Decimal(kcal["estimated_max"])

        # Fill in the unknown meal later; its old items stay as superseded.
        filled = request_json(
            "PUT",
            f"/api/log/entries/{unknown.json()['id']}/items",
            {"items": [{"food": "bls4-c352032", "amount_min": 100, "amount_max": 200}]},
        )
        assert filled.status_code == 200 and filled.json()["status"] == "estimated"

        moved = request_json(
            "PATCH", f"/api/log/entries/{unknown.json()['id']}", {"eaten_at": "2026-01-14T21:00:00"}
        )
        assert moved.json()["eaten_at"].startswith("2026-01-14T21:00:00+01:00")
        assert request(f"/api/log/days/{day}").json()["counts"]["estimated"] == 1

        deleted = request_json("DELETE", f"/api/log/entries/{estimated.json()['id']}", None)
        assert deleted.status_code == 204
        assert request(f"/api/log/entries/{estimated.json()['id']}").status_code == 404

        errors = request_json(
            "POST",
            "/api/log/entries",
            {
                "observation": "x",
                "items": [
                    {"food": "no-such-food", "amount": 1},
                    {"food": food["slug"], "portion": "Teller"},
                ],
            },
        )
        assert errors.status_code == 422
        assert [issue["field"] for issue in errors.json()["detail"]] == [
            "items.0.food",
            "items.1.portion",
        ]
        future = request_json(
            "POST",
            "/api/log/entries",
            {"observation": "x", "eaten_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        )
        assert future.status_code == 422
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "DELETE FROM log.entry_items WHERE entry_id = ANY(%s)", (created_ids,)
            )
            connection.execute("DELETE FROM log.entries WHERE id = ANY(%s)", (created_ids,))
            connection.execute("DELETE FROM foods WHERE barcode = %s", (barcode,))
            connection.execute("REFRESH MATERIALIZED VIEW food_search_terms")
            connection.execute("REFRESH MATERIALIZED VIEW food_search_vocabulary")
