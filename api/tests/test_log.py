import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from health_api.catalog.repository import NUTRIENTS
from health_api.clock import day_bounds
from health_api.log.meals import ItemInput, MealInput
from health_api.nutrition import status, totals
from health_api.recipes.cooks import dish_values
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
        {"food": "x", "amount": 100, "count": 3},
    ],
)
def test_items_need_amount_or_portion_and_no_nutrition(item):
    with pytest.raises(ValidationError):
        ItemInput.model_validate(item)


def test_meals_have_at_most_100_items():
    item = {"food": "x", "amount": 1}
    assert len(MealInput.model_validate({"items": [item] * 100}).items) == 100
    with pytest.raises(ValidationError):
        MealInput.model_validate({"items": [item] * 101})


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


def test_dish_totals_leave_out_ingredients_without_a_value():
    chia = item(30, fiber_g=12.07)
    whey = item(50, protein_g=39)  # its label has no fiber value
    bread = item(120, estimated=True, fiber_g=4)
    values = dish_values([chia, whey, bread])
    assert values["fiber_g"] == Decimal("8.421")  # 3.621 measured + 4.8 estimated
    assert values["protein_g"] == Decimal("19.5")
    assert values["energy_kcal"] is None
    assert dish_values([])["fiber_g"] == 0


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

        dinner = request_json(
            "POST",
            "/api/log/meals",
            {"eaten_at": f"{day}T20:00", "note": "  Italian place, way too much bread  "},
        )
        meal_ids.append(dinner.json()["id"])
        assert dinner.json()["status"] == "unknown" and dinner.json()["kind"] is None
        assert dinner.json()["note"] == "Italian place, way too much bread"

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
        # Other fields keep the note; a blank note clears it.
        assert cleared.json()["note"] == "Italian place, way too much bread"
        blank = request_json("PATCH", f"/api/log/meals/{dinner.json()['id']}", {"note": " "})
        assert blank.json()["note"] is None

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
            connection.execute("SELECT catalog.refresh_search()")


def test_incomplete_days_are_flagged_and_kept_on_the_calendar_against_postgres(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("HEALTH_TIMEZONE", "Europe/Berlin")
    day, empty = "2026-03-20", "2026-03-21"
    meal_ids = []
    try:
        meal = request_json(
            "POST",
            "/api/log/meals",
            {"eaten_at": f"{day}T12:00", "items": [{"food": "bls4-c352032", "amount": 100}]},
        )
        assert meal.status_code == 201, meal.text
        meal_ids.append(meal.json()["id"])
        assert request(f"/api/log/days/{day}").json()["incomplete"] is False

        marked = request_json("PUT", f"/api/log/days/{day}/incomplete", {"incomplete": True})
        assert marked.status_code == 200 and marked.json() == {"date": day, "incomplete": True}
        assert request(f"/api/log/days/{day}").json()["incomplete"] is True

        # A flagged day without meals is still listed, so it can be unflagged on the calendar.
        assert (
            request_json(
                "PUT", f"/api/log/days/{empty}/incomplete", {"incomplete": True}
            ).status_code
            == 200
        )
        calendar = request(f"/api/log/calendar?start={day}&end={empty}").json()
        days = {entry["date"]: entry for entry in calendar["days"]}
        assert days[day]["incomplete"] is True and days[day]["meals"] == 1
        assert days[empty]["incomplete"] is True and days[empty]["meals"] == 0
        assert Decimal(days[empty]["energy_kcal"]["measured"]) == 0

        # Marking twice changes nothing; unmarking brings the day back.
        again = request_json("PUT", f"/api/log/days/{day}/incomplete", {"incomplete": True})
        assert again.status_code == 200
        unmarked = request_json("PUT", f"/api/log/days/{day}/incomplete", {"incomplete": False})
        assert unmarked.json()["incomplete"] is False
        assert request(f"/api/log/days/{day}").json()["incomplete"] is False
        assert (
            request_json(
                "PUT", f"/api/log/days/{day}/incomplete", {"incomplete": "maybe"}
            ).status_code
            == 422
        )
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM log.meals WHERE id = ANY(%s)", (meal_ids,))
            connection.execute(
                "DELETE FROM log.incomplete_days WHERE day IN (%s, %s)", (day, empty)
            )


def test_daily_kcal_limit_is_stored_and_sent_with_the_calendar_against_postgres(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    calendar_path = "/api/log/calendar?start=2026-03-14&end=2026-03-14"
    default = {"daily_kcal_limit": 2000, "kcal_tolerance": 300}  # the migrations' defaults
    try:
        calendar = request(calendar_path).json()
        assert {key: calendar[key] for key in default} == default
        changed = request_json(
            "PUT", "/api/log/goals", {"daily_kcal_limit": 1500, "kcal_tolerance": 200}
        )
        assert changed.status_code == 200
        assert changed.json() == {"daily_kcal_limit": 1500, "kcal_tolerance": 200}
        calendar = request(calendar_path).json()
        assert (calendar["daily_kcal_limit"], calendar["kcal_tolerance"]) == (1500, 200)
        day = request("/api/log/days/2026-03-14").json()
        assert (day["daily_kcal_limit"], day["kcal_tolerance"]) == (1500, 200)
        for invalid in [{"daily_kcal_limit": 0, "kcal_tolerance": 0}, {"daily_kcal_limit": 1500}]:
            rejected = request_json("PUT", "/api/log/goals", invalid)
            assert rejected.status_code == 422, invalid
    finally:
        request_json("PUT", "/api/log/goals", default)


def test_stated_items_count_in_the_day_against_postgres(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("HEALTH_TIMEZONE", "Europe/Berlin")
    day = "2026-03-22"
    meal_ids = []
    protein_bar = {"name": "  Protein bar  ", "energy_kcal": 300, "protein_g": 30}
    try:
        created = request_json(
            "POST",
            "/api/log/meals",
            {"eaten_at": f"{day}T16:00", "kind": "snack", "items": [{"stated": protein_bar}]},
        )
        assert created.status_code == 201, created.text
        meal = created.json()
        meal_ids.append(meal["id"])
        item = meal["items"][0]
        assert item["food"] is None and item["cook_id"] is None
        assert item["food_name"] == "Protein bar"  # the name is trimmed
        assert item["source_name"] == "Stated by you" and item["estimated"] is False
        assert item["nutrition"]["energy_kcal"] == "300"  # whole kcal, as for catalog foods
        assert item["nutrition"]["protein_g"] == "30.00"
        assert item["nutrition"]["fat_g"] is None  # not given, so unknown
        assert meal["status"] == "measured"

        # Stated items count in the day's totals, next to catalog foods.
        food = request_json(
            "POST",
            "/api/log/meals",
            {
                "eaten_at": f"{day}T12:00",
                "items": [{"food": "bls4-c352032", "amount": 100}, {"stated": protein_bar}],
            },
        )
        assert food.status_code == 201, food.text
        meal_ids.append(food.json()["id"])
        summary = request(f"/api/log/days/{day}").json()
        assert Decimal(summary["totals"]["energy_kcal"]["measured"]) > 600
        assert Decimal(summary["totals"]["protein_g"]["measured"]) > 60

        # A guessed figure makes its meal estimated, and the value is marked so.
        guessed = request_json(
            "POST",
            "/api/log/meals",
            {"eaten_at": f"{day}T20:00", "items": [{"stated": protein_bar, "estimated": True}]},
        )
        meal_ids.append(guessed.json()["id"])
        assert guessed.json()["status"] == "estimated"
        summary = request(f"/api/log/days/{day}").json()
        assert Decimal(summary["totals"]["energy_kcal"]["estimated"]) == 300

        # Invalid stated items are refused, with the reason.
        both = request_json(
            "POST",
            "/api/log/meals",
            {"items": [{"food": "bls4-c352032", "amount": 1, "stated": protein_bar}]},
        )
        assert both.status_code == 422
        with_amount = request_json(
            "POST",
            "/api/log/meals",
            {"items": [{"stated": protein_bar | {"name": "x"}, "amount": 1}]},
        )
        assert with_amount.status_code == 422
        blank = request_json(
            "POST", "/api/log/meals", {"items": [{"stated": protein_bar | {"name": "   "}}]}
        )
        assert blank.status_code == 422
        negative = request_json(
            "POST", "/api/log/meals", {"items": [{"stated": protein_bar | {"energy_kcal": -5}}]}
        )
        assert negative.status_code == 422

        # Editing the note keeps the stated item; replacing items removes it.
        noted = request_json("PATCH", f"/api/log/meals/{meal['id']}", {"note": "after the gym"})
        assert [entry["food_name"] for entry in noted.json()["items"]] == ["Protein bar"]
        replaced = request_json("PATCH", f"/api/log/meals/{meal['id']}", {"items": []})
        assert replaced.json()["items"] == [] and replaced.json()["status"] == "unknown"
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM log.meals WHERE id = ANY(%s)", (meal_ids,))


def test_calendar_counts_each_local_day_against_postgres(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("HEALTH_TIMEZONE", "Europe/Berlin")
    meal_ids = []
    try:
        # 23:30 Berlin time is still the 14th; the UTC date is the 14th too, but the local
        # 00:30 meal is the 15th, which only the local clock can tell.
        for eaten_at in ["2026-03-14T23:30", "2026-03-15T00:30"]:
            created = request_json(
                "POST",
                "/api/log/meals",
                {"eaten_at": eaten_at, "items": [{"food": "bls4-c352032", "amount": 100}]},
            )
            assert created.status_code == 201, created.text
            meal_ids.append(created.json()["id"])
        unknown = request_json("POST", "/api/log/meals", {"eaten_at": "2026-03-15T20:00"})
        meal_ids.append(unknown.json()["id"])

        calendar = request("/api/log/calendar?start=2026-03-14&end=2026-03-15").json()
        assert calendar["timezone"] == "Europe/Berlin"
        days = {day["date"]: day for day in calendar["days"]}
        assert set(days) == {"2026-03-14", "2026-03-15"}
        assert days["2026-03-14"]["meals"] == 1 and days["2026-03-14"]["unknown_meals"] == 0
        assert days["2026-03-15"]["meals"] == 2 and days["2026-03-15"]["unknown_meals"] == 1
        # The 15th holds one measured meal of the same food, plus an unknown one.
        assert Decimal(days["2026-03-14"]["energy_kcal"]["measured"]) > 0
        assert (
            days["2026-03-15"]["energy_kcal"]["measured"]
            == days["2026-03-14"]["energy_kcal"]["measured"]
        )

        assert request("/api/log/calendar?start=2026-03-15&end=2026-03-14").status_code == 422
        assert request("/api/log/calendar?start=2026-01-01&end=2027-03-01").status_code == 422
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM log.meals WHERE id = ANY(%s)", (meal_ids,))
