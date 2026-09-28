import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from health_api.catalog.repository import NUTRIENTS
from health_api.log.meals import ItemInput, MealInput, day_bounds, status, totals
from pydantic import ValidationError
from test_catalog import request
from test_registration import QUARK, request_json


@pytest.mark.parametrize(
    "item",
    [
        {"food": "x"},
        {"food": "x", "amount": 100, "portion": "Becher"},
        {"food": "x", "amount": 0},
        {"food": "x", "amount": 100, "energy_kcal": 500},
        {"food": "x", "amount_min": 100, "amount_max": 150},
    ],
)
def test_items_need_amount_or_portion_and_no_nutrition(item):
    with pytest.raises(ValidationError):
        ItemInput.model_validate(item)


def test_meal_kinds_are_fixed():
    assert MealInput.model_validate({"kind": "lunch"}).kind == "lunch"
    with pytest.raises(ValidationError):
        MealInput.model_validate({"kind": "second breakfast"})


def item(amount, estimated=False, **nutrition):
    return {
        "amount": Decimal(amount),
        "reference_quantity": Decimal(100),
        "estimated": estimated,
        **{column: None for column in NUTRIENTS},
        **{key: Decimal(str(value)) for key, value in nutrition.items()},
    }


def test_status_and_totals_keep_measured_and_estimated_apart():
    cup = item(400, energy_kcal=68, protein_g="12.4")
    bread = item(120, estimated=True, energy_kcal=250)
    assert status([]) == "unknown"
    assert status([cup]) == "measured"
    assert status([cup, bread]) == "estimated"
    result = totals([cup, bread])
    assert result["energy_kcal"] == {
        "measured": "272",
        "estimated": "300",
        "items_without_value": 0,
    }
    assert result["protein_g"] == {
        "measured": "49.60",
        "estimated": "0.00",
        "items_without_value": 1,
    }


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
    meal_ids = []
    try:
        food = request_json(
            "POST", "/api/foods", QUARK | {"name": "Log test quark", "barcode": barcode}
        ).json()["food"]
        cup = {"food": food["slug"], "portion": "becher"}

        dry = request_json(
            "POST", "/api/log/meals?dry_run=true", {"eaten_at": f"{day}T08:00", "items": [cup]}
        )
        assert dry.status_code == 200 and dry.json()["totals"]["protein_g"]["measured"] == "49.60"
        assert request(f"/api/log/days/{day}").json()["meals"] == []

        breakfast = request_json(
            "POST",
            "/api/log/meals",
            {"eaten_at": f"{day}T08:00", "kind": "breakfast", "items": [cup]},
        )
        assert breakfast.status_code == 201, breakfast.text
        meal_ids.append(breakfast.json()["id"])
        assert breakfast.json()["status"] == "measured"
        assert breakfast.json()["items"][0]["amount"] == "400"
        assert breakfast.json()["items"][0]["nutrition"]["energy_kcal"] == "272"

        lunch = request_json(
            "POST",
            "/api/log/meals",
            {
                "eaten_at": f"{day}T13:00:00+01:00",
                "kind": "lunch",
                "items": [
                    {"food": "bls4-c352032", "amount": 200, "estimated": True},
                    {"food": "bls4-g312132", "amount": 100},
                ],
            },
        )
        assert lunch.status_code == 201, lunch.text
        meal_ids.append(lunch.json()["id"])
        assert lunch.json()["status"] == "estimated"

        dinner = request_json("POST", "/api/log/meals", {"eaten_at": f"{day}T20:00"})
        meal_ids.append(dinner.json()["id"])
        assert dinner.json()["status"] == "unknown" and dinner.json()["kind"] is None

        summary = request(f"/api/log/days/{day}").json()
        assert summary["counts"] == {"measured": 1, "estimated": 1, "unknown": 1}
        kcal = summary["totals"]["energy_kcal"]
        assert Decimal(kcal["measured"]) > 272 and Decimal(kcal["estimated"]) > 0

        filled = request_json(
            "PATCH",
            f"/api/log/meals/{dinner.json()['id']}",
            {"kind": "dinner", "items": [{"food": "bls4-c352032", "amount": 150}]},
        )
        assert filled.status_code == 200, filled.text
        assert filled.json()["status"] == "measured" and filled.json()["kind"] == "dinner"
        cleared = request_json("PATCH", f"/api/log/meals/{dinner.json()['id']}", {"kind": None})
        assert cleared.json()["kind"] is None and len(cleared.json()["items"]) == 1

        moved = request_json(
            "PATCH", f"/api/log/meals/{dinner.json()['id']}", {"eaten_at": "2026-01-14T21:00"}
        )
        assert moved.json()["eaten_at"].startswith("2026-01-14T21:00:00+01:00")
        assert request(f"/api/log/days/{day}").json()["counts"]["measured"] == 1

        assert (
            request_json("DELETE", f"/api/log/meals/{lunch.json()['id']}", None).status_code == 204
        )
        assert request(f"/api/log/meals/{lunch.json()['id']}").status_code == 404

        errors = request_json(
            "POST",
            "/api/log/meals",
            {"items": [{"food": "no-such-food", "amount": 1}, {**cup, "portion": "Teller"}]},
        )
        assert errors.status_code == 422
        assert [issue["field"] for issue in errors.json()["detail"]] == [
            "items.0.food",
            "items.1.portion",
        ]
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        assert request_json("POST", "/api/log/meals", {"eaten_at": future}).status_code == 422
        assert request_json("PATCH", "/api/log/meals/0", {"kind": "snack"}).status_code == 404
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM log.meals WHERE id = ANY(%s)", (meal_ids,))
            connection.execute("DELETE FROM catalog.foods WHERE barcode = %s", (barcode,))
            connection.execute("REFRESH MATERIALIZED VIEW catalog.food_search_terms")
            connection.execute("REFRESH MATERIALIZED VIEW catalog.food_search_vocabulary")
