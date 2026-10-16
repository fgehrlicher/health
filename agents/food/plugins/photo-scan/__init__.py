"""Photo scan: reads barcodes and QR codes in incoming photos before the agent sees the message.

Each photo is sent to the health API's `POST /api/scan`, which decodes the codes
and checks them against the catalog. What it found is added to the message text
as a "[photo scan]" block, so the agent works from codes that were read by a
decoder rather than digits it read from the picture itself.

Standard library only: the decoder runs in the API, not in the Hermes runtime.
Every scan is logged to logs/photo-scan.jsonl in the profile. A failure never
blocks a message: the message goes on unchanged.
"""

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
API = os.environ.get("HEALTH_API_URL", "http://127.0.0.1:8000")
IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
LINEAR_FORMATS = {"EAN-13", "EAN-8", "UPC-A"}
# A QR code's text reaches the agent as data; long or multi-line text is cut down.
MAX_TEXT = 200
# The plugin lives in <profile>/plugins/photo-scan, so its log goes to <profile>/logs.
# (The gateway process's HERMES_HOME is the default home, not the food profile.)
LOG = HERE.parent.parent / "logs" / "photo-scan.jsonl"


def _log(record: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    entry = {"at": now.isoformat(timespec="seconds"), **record}
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _scan(path: Path) -> list[dict]:
    """The codes the API finds in one photo, each with its catalog status."""
    call = urllib.request.Request(
        f"{API}/api/scan",
        data=path.read_bytes(),
        method="POST",
        headers={"Content-Type": IMAGE_TYPES[path.suffix.lower()], "Accept": "application/json"},
    )
    with urllib.request.urlopen(call, timeout=20) as response:
        return json.load(response)["codes"]


def _shown(text: str) -> str:
    """A code's text on one line, cut to MAX_TEXT characters."""
    line = " ".join(text.split())
    return line if len(line) <= MAX_TEXT else line[:MAX_TEXT] + "…"


def _line(code: dict) -> str:
    """One code as one line of the scan block, with what the catalog knows about it."""
    kind = "QR code" if code["format"] == "QR Code" else code["format"]
    number = code["product_number"]
    if code["status"] == "no_product_number" or number is None:
        return f"- {kind}, no product number: {_shown(code['text'])}"
    label = kind if code["format"] in LINEAR_FORMATS else f"product number from {kind}"
    if code["status"] == "known":
        food = code["food"]
        found = f'known product "{food["name"]}" (slug {food["slug"]})'
    elif code["status"] == "not_in_catalog":
        found = "not in the catalog yet"
    elif code["status"] == "in_store_code":
        found = "an in-store code (e.g. weighed goods), not a product"
    else:  # misread
        found = "check digit wrong, probably misread; ask for a closer photo"
    return f"- {label} {number}: {found}"


def _on_pre_gateway_dispatch(event=None, **_kwargs):
    try:
        media = [Path(path) for path in getattr(event, "media_urls", None) or []]
        photos = [path for path in media if path.suffix.lower() in IMAGE_TYPES]
        if not photos:
            return None
        scans = [{"file": photo.name, "codes": _scan(photo)} for photo in photos]
        _log({"message_type": str(getattr(event, "message_type", "")), "scans": scans})
        lines = [_line(code) for scan in scans for code in scan["codes"]]
        if not lines:
            return None
        text = (getattr(event, "text", "") or "").rstrip()
        block = "[photo scan]\n" + "\n".join(lines)
        return {"action": "rewrite", "text": f"{text}\n\n{block}" if text else block}
    except Exception as error:  # noqa: BLE001 - fail open: the message goes on unchanged
        _log({"error": repr(error)[:300]})
        return None


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
