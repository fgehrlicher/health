"""Post-processing of the imported USDA foods: a food group and a German name for each.

The decisions are made by an LLM, one batch at a time, following PROMPT.md. This
module exports the batches, checks the decisions, and writes them to the database.
Every USDA food needs exactly one decision, or nothing is written.
"""

import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from usda_importer.bundle import DATA_TYPES, PINNED, Archive
from usda_importer.source import SOURCE_NAME

POST_DIR = Path(__file__).resolve().parents[2] / "postprocess"
GROUPS_PATH = POST_DIR / "groups.json"
PROMPT_PATH = POST_DIR / "PROMPT.md"
DECISIONS_DIR = POST_DIR / "decisions"
BATCH_SIZE = 400


def categories_by_fdc(data_dir: Path) -> dict[int, str]:
    """The USDA food category of each imported record, from the pinned archives."""
    categories: dict[int, str] = {}
    for file_name, (dataset, _sha256) in PINNED.items():
        archive = Archive(data_dir / file_name)
        names = {row["id"]: row["description"] for row in archive.rows("food_category.csv")}
        for row in archive.rows("food.csv"):
            if row["data_type"] == DATA_TYPES[dataset]:
                categories[int(row["fdc_id"])] = names.get(row.get("food_category_id") or "", "")
    return categories


def export_batches(
    database_url: str, data_dir: Path, out_dir: Path, batch_size: int = BATCH_SIZE
) -> int:
    """Write the USDA foods, in batches, for the LLM to decide. Returns the food count."""
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        rows = connection.execute(
            """SELECT f.slug, f.name, f.preparation_state, s.external_id
               FROM catalog.foods f JOIN catalog.food_sources s ON s.food_id = f.id
               WHERE s.source_name = %s
               ORDER BY s.external_id::bigint""",
            (SOURCE_NAME,),
        ).fetchall()
    categories = categories_by_fdc(data_dir)
    items = [
        {
            "slug": row["slug"],
            "name": row["name"],
            "usda_category": categories.get(int(row["external_id"]), ""),
            "preparation_state": row["preparation_state"],
        }
        for row in rows
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    for index in range(0, len(items), batch_size):
        path = out_dir / f"batch-{index // batch_size + 1:02d}.json"
        path.write_text(
            json.dumps(items[index : index + batch_size], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    return len(items)


def load_decisions(decisions_dir: Path) -> list[dict]:
    decisions: list[dict] = []
    for path in sorted(decisions_dir.glob("batch-*.json")):
        decisions.extend(json.loads(path.read_text(encoding="utf-8")))
    return decisions


def load_groups(path: Path) -> dict[str, str]:
    """The German name of each food group, by code."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {code: entry["name_de"] for code, entry in data.items()}


def check_decisions(decisions: list[dict], expected: set[str], codes: set[str]) -> list[str]:
    """Every problem found: a missing, repeated, unknown or malformed decision."""
    problems: list[str] = []
    seen: set[str] = set()
    for item in decisions:
        slug = item.get("slug", "")
        if slug in seen:
            problems.append(f"{slug}: decided more than once")
        seen.add(slug)
        if slug not in expected:
            problems.append(f"{slug}: not an imported USDA food")
        if item.get("food_group") not in codes:
            problems.append(f"{slug}: food group {item.get('food_group')!r} is not a catalog group")
        name = item.get("name_de") or ""
        if not name or name != name.strip() or len(name) > 200:
            problems.append(f"{slug}: German name is missing or malformed")
    missing = sorted(expected - seen)
    if missing:
        problems.append(f"{len(missing)} foods have no decision, for example {missing[:3]}")
    return problems


def apply(database_url: str, decisions_dir: Path, groups_path: Path, commit: bool) -> dict:
    """Check the decisions and, with commit, write them. Returns a summary."""
    decisions = load_decisions(decisions_dir)
    groups = load_groups(groups_path)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        codes = {row["code"] for row in connection.execute("SELECT code FROM catalog.food_groups")}
        expected = {
            row["slug"]
            for row in connection.execute(
                """SELECT f.slug FROM catalog.foods f
                   JOIN catalog.food_sources s ON s.food_id = f.id
                   WHERE s.source_name = %s""",
                (SOURCE_NAME,),
            )
        }
        problems = check_decisions(decisions, expected, codes)
        if set(groups) != codes:
            problems.append("the group translations do not match the catalog's groups")
        if problems:
            raise ValueError(
                "; ".join(problems[:20])
                + (f" (and {len(problems) - 20} more)" if len(problems) > 20 else "")
            )
        if commit:
            with connection.transaction():
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext('health:usda-postprocess')::bigint)"
                )
                for code, name in groups.items():
                    connection.execute(
                        "UPDATE catalog.food_groups SET name_de = %s WHERE code = %s", (name, code)
                    )
                for item in decisions:
                    connection.execute(
                        """UPDATE catalog.foods SET
                               food_group = %(group)s,
                               name_de = %(name)s,
                               aliases = CASE WHEN %(name)s = ANY(aliases) THEN aliases
                                              ELSE array_append(aliases, %(name)s) END
                           WHERE slug = %(slug)s""",
                        {
                            "group": item["food_group"],
                            "name": item["name_de"],
                            "slug": item["slug"],
                        },
                    )
                connection.execute("SELECT catalog.refresh_search()")
    return {
        "dry_run": not commit,
        "decisions": len(decisions),
        "foods": len(expected),
        "groups": len(groups),
        "groups_used": dict(sorted(_count(decisions, "food_group").items())),
    }


def _count(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item[key]] = counts.get(item[key], 0) + 1
    return counts
