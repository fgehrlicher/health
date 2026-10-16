# Scan tool: barcodes and QR codes in photos

Status: **built and live-tested.** Every photo sent to the food bot is scanned
before the agent sees the message. The research and the spike that led here are
kept below.

**Live check after the build (2026-10-16, 23:42):** a Telegram photo of the
Bio-Skyr cup went through the deployed plugin and the API. The scan log has the
new format, and the agent's message ended with
`- EAN-13 4104060030772: not in the catalog yet`. The agent named the barcode,
logged nothing, made no tool call, and asked whether and how much he had eaten.

## Why

The food agent reads barcodes from photos by looking at them, and it gets digits
wrong. A deterministic decoder reads the code, checks the check digit, and passes
the number on. The agent then works from what was read.

## How it works

**The API decodes.** `POST /api/scan` (`api/src/health_api/scan.py`) takes the
image bytes as the body, with `Content-Type` `image/jpeg`, `image/png` or
`image/webp`, up to 10 MB. It turns the photo upright from its EXIF orientation,
decodes it with zxing-cpp, and checks each code against the catalog:

```json
{"codes": [{"format": "EAN-13", "text": "4104060030772",
            "product_number": "4104060030772", "status": "known",
            "food": {"slug": "…", "name": "…"}}]}
```

| Status | Meaning |
|---|---|
| `known` | the product number is in the catalog; `food` names it |
| `not_in_catalog` | a valid product number the catalog does not have yet |
| `in_store_code` | a shop's own code (prefix 2, e.g. weighed goods), not a product |
| `misread` | the check digit is wrong |
| `no_product_number` | e.g. a QR code that only links somewhere |

A product number is the EAN-13, EAN-8 or UPC-A itself, or the GTIN a GS1 Digital
Link QR code carries (see "QR codes" below). The check-digit and in-store rules are
the same ones product registration uses (`barcode_issue` in
`catalog/registration.py`). A photo without a readable code gives an empty list.
Errors: 415 for another content type, 413 for a larger image, 422 for bytes that
are not a readable image.

**The CLI.** `health scan --image photo.jpg` sends a photo to that endpoint and
prints the result. It refuses other file types before calling the API (exit 2).

**The plugin.** `agents/food/plugins/photo-scan/` is a Hermes plugin on the
`pre_gateway_dispatch` hook. It is standard library only: it sends each photo of
an incoming message to `/api/scan` and adds what was found to the message text:

```
[photo scan]
- EAN-13 4056489417927: known product "Lidl Heißgeräucherte Forellenfilets mit Pfeffer" (slug …)
- product number from QR code 4333844022041: not in the catalog yet
- EAN-8 20123459: an in-store code (e.g. weighed goods), not a product
- product number from QR code 4000000000052: check digit wrong, probably misread; ask for a closer photo
- QR code, no product number: https://www.oetker.de/rezepte
```

- A photo without codes, or a message without photos, is left unchanged.
- A QR code's text is shown on one line and cut to 200 characters, so it cannot
  add lines of its own to the block.
- Every scan is logged to `logs/photo-scan.jsonl` in the food profile, with the
  file name and the API's answer. Errors are logged the same way.
- **It fails open:** if the API is down or anything else fails, the message goes
  on unchanged.

**The agent's rules** are in the food skill (`SKILL.md`, "Photos"): use a known
product's slug directly; search the name, then ask for a label photo, for a
product not in the catalog; an in-store code is not a product; ask for a closer
photo on a misread; never open a QR link. Digits the agent reads itself count only
after `health foods barcode` accepts them.

**Deploy.** `scripts/deploy-health-box.sh` replaces the plugin folder in the food
profile with the repo's copy, then disables and enables the plugin, which makes
the running gateway load the new code without a restart.

## What we measured

Test set: the 75 photos the food profile cached from Telegram (960×1280 JPEG,
which is how Telegram compresses them). Local copies lived in a scratch folder
and were not committed.

| Decoder | Photos with a readable code | Notes |
|---|---|---|
| zxing-cpp (Python binding) | 26 of 75 | 20 EAN-13, 4 EAN-8, 4 QR; ~14 ms per photo |
| zbar 0.23.95 (`zbarimg`) | 24 of 75 | Read nothing zxing missed; ~48 ms per photo with process start |
| OpenCV QR detector | 2 of 75 | Weaker on QR |
| OpenCV barcode module | 0 of 75 | Not usable |

**Decision: zxing-cpp.** It read everything zbar read, plus two more, and runs
in-process in Python. Through the endpoint, real photos took 22–61 ms.

**Trust:** all 20 EAN-13 and EAN-8 codes zxing read had valid check digits, so a
read is a strong sign of correctness.

**Catalog check** (read-only lookups against the box's API), on the 18 distinct
codes: 11 are known products, 7 are not in the catalog yet. One EAN-8 starting
with 2 is an in-store code, which the API correctly refuses as a product.

**Why 49 photos gave no result.** I looked at three:
- two showed no code in the frame (the front of a bar, and a box front);
- one showed a real EAN-13, on a curved cup, tilted, with glare. Rotations of
  90/180/270 degrees, upscaling, contrast, sharpening, binarising and a tilt sweep
  of ±40 degrees all failed on it.

I did not check the other 46 one by one.

**QR codes.** The Lidl fish QR code is a GS1 Digital Link:
`https://www.lidl.de/de/fischtracking/s4306?01=04333844022041`. The product number
follows application identifier `01`, in the path (`/01/<gtin>`) or the query
(`?01=<gtin>`). Its 14 digits carry a leading zero, so it is the EAN-13
`4333844022041`. The other QR codes were a Dr. Oetker link and an iglo tracking
link, which carry no product number.

Sources: [GS1 UK on Digital Link QR codes](https://gs1uk.org/standards-services/get-market-ready/connect-to-consumer/guides-resources/how-to-create-a-gs1-digital-link-url-for-a-qr-code),
[GS1 Digital Link quick start](https://ref.gs1.org/docs/2024/digital-link-quick-start-guide).
GS1 sources disagree on GTIN padding in those URLs, so check the GS1 specification
before relying on the padding rule for anything beyond the cases above.

## How Hermes can see a photo

- Photos reach the model as pixels, or as a text description from the vision step.
  The description ends with the photo's cache path
  (`[If you need a closer look, use vision_analyze with image_url: <path>]`), so
  the agent can pass that path to `health scan --image`.
- **Shell hooks cannot help.** Their events (`pre_llm_call` and the others) do not
  carry media paths.
- **A Python plugin on `pre_gateway_dispatch` can.** The event carries `media_urls`,
  which the Telegram adapter fills with local cache paths. The hook can return
  `{"action": "rewrite", "text": …}` to replace the message text the agent receives.
- The gateway process runs with the default Hermes home, not the food profile's,
  so the plugin finds its log folder from its own location.

## The spike's live check: passed

The spike decoded in the plugin itself, with zxing-cpp in a scratch folder on the
box. A Telegram photo of a Milbona yogurt cup, with the text "Das ist ein Test,
bitte nicht eintragen" ("this is a test, don't log it"), was sent to the food bot.

- The hook read the EAN-13 `4335619151208` (check digit valid) and added
  `- EAN-13 4335619151208: not in the catalog yet` to the message.
- The stored user message, as the model received it, had three parts: the vision
  description of the photo, the user's text, and the `[photo scan]` block.
- The vision description also read the printed digits, `4 335619 151208`, which
  agree with the decoder.
- The agent replied "Verstanden, ich trage das nicht ein" ("understood, I won't
  log that") and made no tool call.
- A second photo (a Bio-Skyr cup, EAN-13 `4104060030772`) confirmed that the scan
  log is written to the food profile.

## Decisions

1. **The decoder runs in the API**, not in the Hermes runtime. zxing-cpp
   (Apache-2.0) and Pillow (MIT-CMU) are pinned in `uv.lock` and installed in the
   API image. The plugin and the CLI need only the standard library.
2. **The catalog lookup is part of the scan.** The endpoint answers with each
   code's status, so the plugin, the CLI and the agent all get the same answer in
   one step, and the agent has one step fewer to get wrong.
3. **QR links are shown, never opened.**

## Open items

- **Unknown products:** a code not in the catalog should lead to a lookup on Open
  Food Facts (backlog item 1), and then to a label photo if that finds nothing.
- **Hard cases:** curved or glared codes still fail. A closer photo is the fix.
