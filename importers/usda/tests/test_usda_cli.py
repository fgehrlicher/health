import json
from pathlib import Path

import pytest
from test_usda_bundle import (
    FOUNDATION_NAME,
    SR_NAME,
    food,
    label_values,
    make_archive,
    portion,
    sha256,
)
from usda_importer import bundle, cli


@pytest.fixture
def archives(tmp_path, monkeypatch):
    """One SR Legacy archive with two foods, pinned to its real checksum."""
    foods = [
        food(169997, "Coriander (cilantro) leaves, raw"),
        food(171328, "Spices, oregano, dried"),
    ]
    amounts = label_values(169997) + label_values(171328)
    portions = [portion(169997, 1, "cup", 28)]
    path = make_archive(tmp_path, SR_NAME, foods=foods, amounts=amounts, portions=portions)
    pinned = {SR_NAME: ("sr_legacy", sha256(path))}
    monkeypatch.setattr(cli, "PINNED", pinned)
    monkeypatch.setattr(bundle, "PINNED", pinned)
    return tmp_path


def test_dry_run_reads_the_archives_and_writes_nothing(archives, monkeypatch):
    monkeypatch.setattr(cli, "write_foods", lambda *_: pytest.fail("a dry run must not write"))
    summary = cli.run(["--data-dir", str(archives)])
    assert summary["dry_run"] is True
    assert summary["selected"] == 2
    assert (summary["created"], summary["updated"]) == (0, 0)
    assert summary["rejected_count"] == 0


def test_the_german_alias_comes_from_the_names_file(archives):
    report_path = archives / "report.json"
    cli.run(["--data-dir", str(archives), "--report", str(report_path)])
    foods = {f["fdc_id"]: f for f in json.loads(report_path.read_text(encoding="utf-8"))["foods"]}
    assert foods[169997]["name_de"] == "Koriander, frisch (Blätter)"
    assert foods[171328]["name_de"] == "Oregano, getrocknet"


def test_the_full_report_lists_every_food_and_the_portions(archives):
    report_path = archives / "report.json"
    summary = cli.run(["--data-dir", str(archives), "--report", str(report_path)])
    full = json.loads(report_path.read_text(encoding="utf-8"))
    assert summary["report_file"] == str(report_path)
    assert {f["slug"] for f in full["foods"]} == {"usda-169997", "usda-171328"}
    assert next(f for f in full["foods"] if f["fdc_id"] == 169997)["portions"] == 1


def test_commit_hands_the_foods_to_the_writer(archives, monkeypatch):
    stored = []

    def fake_write(url, foods):
        stored.extend(food.fdc_id for food in foods)
        return (2, 0)

    monkeypatch.setattr(cli, "write_foods", fake_write)
    monkeypatch.setenv("DATABASE_URL", "postgres://example/health")
    summary = cli.run(["--data-dir", str(archives), "--commit"])
    assert sorted(stored) == [169997, 171328]
    assert summary["dry_run"] is False
    assert summary["created"] == 2


def test_a_missing_archive_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "PINNED", {SR_NAME: ("sr_legacy", "0" * 64)})
    with pytest.raises(ValueError, match="missing archive"):
        cli.run(["--data-dir", str(tmp_path)])


@pytest.mark.skipif(
    not all(
        (Path(__file__).resolve().parents[3] / "data/usda/raw" / name).exists()
        for name in (SR_NAME, FOUNDATION_NAME)
    ),
    reason="real USDA archives not downloaded",
)
def test_the_real_dry_run_selects_about_the_expected_foods():
    summary = cli.run([])
    assert summary["dry_run"] is True
    assert summary["selected"] > 6500
    assert summary["rejected_count"] < 100
