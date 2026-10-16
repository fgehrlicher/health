"""Photo scan: reads barcodes and QR codes in incoming photos before the agent sees the message.

The codes the decoder read are added to the message text as a "[photo scan]"
block. The agent then works from what was read, and checks any product number
against the catalog, instead of reading digits from the picture itself.

Every scan is logged to logs/photo-scan.jsonl in the profile. A failure never
blocks a message: the message goes on unchanged.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DECODE = HERE / "decode.py"
DECODER_LIB = os.environ.get("PHOTO_SCAN_LIB", str(Path.home() / "scan-spike" / "lib"))
API = os.environ.get("HEALTH_API_URL", "http://127.0.0.1:8000")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
# The plugin lives in <profile>/plugins/photo-scan, so its log goes to <profile>/logs.
# (The gateway process's HERMES_HOME is the default home, not the food profile.)
LOG = HERE.parent.parent / "logs" / "photo-scan.jsonl"


def _log(record: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    entry = {"at": now.isoformat(timespec="seconds"), **record}
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _decode(path: str) -> list[dict]:
    env = {**os.environ, "PYTHONPATH": DECODER_LIB}
    done = subprocess.run(
        [sys.executable, str(DECODE), path],
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr[-300:])
    return json.loads(done.stdout)["codes"]


def _catalog(code: str) -> str:
    """What the app knows about a product number."""
    try:
        with urllib.request.urlopen(f"{API}/api/foods/barcode/{code}", timeout=3) as response:
            return f'known product "{json.load(response)["name"]}"'
    except urllib.error.HTTPError as error:
        messages = {404: "not in the catalog yet", 422: "an in-store code, not a product"}
        return messages.get(error.code, f"lookup failed ({error.code})")
    except OSError:
        return "catalog lookup unavailable"


def _line(code: dict) -> str:
    """One code as one line of the scan block, with what the app knows about it."""
    if code["format"] == "QR Code" and code["gtin"] is None:
        return f"- QR code, no product number: {code['text']}"
    value = code["gtin"] or code["text"]
    if code["checksum_ok"] is False:
        return f"- {value}: check digit wrong, probably misread; ask for a closer photo"
    kind = "product number from QR code" if code["gtin"] else code["format"]
    return f"- {kind} {value}: {_catalog(value)}"


def _on_pre_gateway_dispatch(event=None, **_kwargs):
    try:
        media = getattr(event, "media_urls", None) or []
        paths = [path for path in media if Path(path).suffix.lower() in IMAGE_SUFFIXES]
        if not paths:
            return None
        scans = [{"file": Path(path).name, "codes": _decode(path)} for path in paths]
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
