import pytest
from bls4_importer import download


def test_package_with_wrong_checksum_is_discarded(tmp_path, monkeypatch):
    fake = tmp_path / "fake.zip"
    fake.write_bytes(b"not the BLS package")
    monkeypatch.setattr(download, "ZIP_URL", fake.as_uri())
    package = tmp_path / "data/BLS_4_0_2025_DE.zip"
    workbook = tmp_path / "data/BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx"

    with pytest.raises(ValueError, match="checksum"):
        download.ensure_workbook(workbook, package)
    assert list(package.parent.iterdir()) == []
    assert not workbook.exists()
