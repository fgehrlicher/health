"""Fetch the pinned official BLS 4.0 package when it is not on disk."""

import hashlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ZIP_URL = "https://blsdb.de/assets/uploads/BLS_4_0_2025_DE.zip"
ZIP_SHA256 = "12b7a6ba62807ec9b301eb276f897dc85f99b2292311618dec3749a12d984c91"
WORKBOOK_MEMBER = "BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_zip(target: Path) -> None:
    """Download to a temporary file and move it into place only if the checksum matches."""
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {ZIP_URL}", file=sys.stderr)
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as part:
        part_path = Path(part.name)
        try:
            with urllib.request.urlopen(ZIP_URL, timeout=60) as response:
                shutil.copyfileobj(response, part)
        except BaseException:
            part_path.unlink(missing_ok=True)
            raise
    zip_hash = sha256_file(part_path)
    if zip_hash != ZIP_SHA256:
        part_path.unlink()
        raise ValueError(f"unexpected BLS package checksum: {zip_hash}; expected {ZIP_SHA256}")
    part_path.replace(target)


def ensure_workbook(workbook: Path, package: Path) -> None:
    """Extract the workbook from the package, downloading the package if needed."""
    if workbook.exists():
        return
    if not package.exists():
        download_zip(package)
    elif sha256_file(package) != ZIP_SHA256:
        raise ValueError(f"unexpected BLS package checksum for {package}; delete it to re-download")
    with zipfile.ZipFile(package) as archive, archive.open(WORKBOOK_MEMBER) as source:
        workbook.parent.mkdir(parents=True, exist_ok=True)
        part_path = workbook.with_suffix(".part")
        with part_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        part_path.replace(workbook)
