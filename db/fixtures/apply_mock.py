"""One-off: copy the example product and day from mock.json into this database.

Run once after the BLS import, then delete this file and mock.json:

    uv run --locked python db/fixtures/apply_mock.py

The meals keep their original day, 2026-09-30. Everything goes through the API's
own routes.
"""

import asyncio
import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from health_api.app import app

mock = json.loads((Path(__file__).parent / "mock.json").read_text(encoding="utf-8"))
DAY = date(2026, 9, 30)
ZONE = ZoneInfo("Europe/Berlin")


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        for food in mock["foods"]:
            body = {key: value for key, value in food.items() if key != "slug"}
            response = await client.post("/api/foods", json=body)
            if response.status_code not in (201, 409):
                raise SystemExit(f"{food['slug']}: {response.status_code} {response.text}")
            print(f"{food['slug']}: {response.status_code}")
        for meal in mock["meals"]:
            eaten_at = datetime.combine(DAY, time.fromisoformat(meal["time"]), ZONE)
            body = {key: value for key, value in meal.items() if key != "time"}
            response = await client.post(
                "/api/log/meals", json=body | {"eaten_at": eaten_at.isoformat()}
            )
            if response.status_code != 201:
                raise SystemExit(f"meal at {meal['time']}: {response.status_code} {response.text}")
        print(f"logged {len(mock['meals'])} meals on {DAY}")


asyncio.run(main())
