# Scan tool: barcodes and QR codes in photos

Status: **spike, partly tested.** The Hermes hook works offline on real photos and
is enabled on the food profile. The live check is still open: it needs a Telegram
photo with a code, sent to the food bot (see "Live check" below).

## Why

The food agent reads barcodes from photos by looking at them, and it gets digits
wrong. A deterministic decoder reads the code, checks the check digit, and passes
the number on. The agent then works from what was read.

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
in-process in Python.

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

- The agent never receives a file path. Photos reach the model as pixels, or as a
  text description from the vision step.
- **Shell hooks cannot help.** Their events (`pre_llm_call` and the others) do not
  carry media paths.
- **A Python plugin on `pre_gateway_dispatch` can.** The event carries `media_urls`,
  which the Telegram adapter fills with local cache paths. The hook can return
  `{"action": "rewrite", "text": …}` to replace the message text the agent receives.

So the plugin decodes each incoming photo and appends the result to the message as
a `[photo scan]` block. This happens before the agent runs, so the agent does not
have to decide to scan.

## The spike (what is on the box)

- **Plugin:** `agents/food/plugins/photo-scan/` in the repo (`plugin.yaml`,
  `__init__.py`, `decode.py`). It is copied to
  `~/.hermes/profiles/food/plugins/photo-scan/` on the box.
- **Decoder environment:** `~/scan-spike/lib` on the box holds zxing-cpp and Pillow,
  installed into a scratch folder with the Hermes runtime's own Python. The Hermes
  packages themselves were not changed. The plugin runs `decode.py` as a subprocess
  with that folder on `PYTHONPATH`.
- **Enabled:** `hermes -p food plugins enable photo-scan`. The gateway reloaded it
  without a restart, since `pre_gateway_dispatch` is a gateway transform hook.
- **Logs:** every scan is written to
  `~/.hermes/profiles/food/logs/photo-scan.jsonl`, with the file name, the codes
  found, and the decoder's raw output. Failures are logged the same way.
- **Failure policy:** if anything fails, the message goes on unchanged.

### What the hook adds

For a photo with codes, the message gets a block like this:

```
[photo scan]
- EAN-13 4056489417927: known product "Lidl Heißgeräucherte Forellenfilets mit Pfeffer"
- product number from QR code 4333844022041: not in the catalog yet
```

- A known product name comes from the catalog lookup.
- A code with a wrong check digit is reported as probably misread, and the agent
  is told to ask for a closer photo.
- A photo with no codes leaves the message unchanged.

### Offline test (run on the box, real cached photos)

| Case | Result |
|---|---|
| Two EAN-13 codes in one photo | both listed, one known, one not in catalog |
| One known EAN-13 | known product named |
| One EAN-8 | known product named (Duplo) |
| Lidl QR with GS1 product number, plus an EAN-13 | both listed, product number extracted |
| Photo without a readable code | no change to the message |
| Text-only message | no change to the message |

## Live check (still open)

Send one Telegram photo with a barcode to the food bot. Use a known product photo
or a new one. Then:

1. Check `~/.hermes/profiles/food/logs/photo-scan.jsonl` on the box for a new line
   with the file name and the codes.
2. Check the agent's reply: it should use the `[photo scan]` result, not guess the
   digits.

If the log has no new line, the Telegram photo is not reaching the hook. In that
case, check the gateway log and the `media_urls` contents before changing the
plugin.

## Open items

- **Deploy path:** the plugin is copied to the box by hand. The deploy script must
  install it into the food profile, and the decoder environment must be set up
  there too, before the next deploy.
- **Dependency:** the decoder environment is a plain folder, not a managed
  environment. Decide whether it stays that way or moves to a pinned install.
- **Licence:** check zxing-cpp's licence before shipping it.
- **Lookup placement:** the plugin does the catalog lookup itself. The alternative
  is to leave the lookup to the agent, which already has `health foods barcode`.
  The plugin version is faster and removes one step the agent could get wrong.
- **Unknown products:** a code not in the catalog should lead to a lookup on Open
  Food Facts (backlog item 2), and then to a label photo if that finds nothing.
- **Vision fallback:** a photo with no readable code may still show a product name,
  which the agent can use for a search. Digits the model reads must pass the check
  digit and the catalog lookup before anything is logged.
- **QR policy:** show the URL, never open it.
- **Hard cases:** curved or glared codes still fail. A closer photo is the fix.

## Decisions needed

1. Accept the decoder dependency (zxing-cpp) in the API image, if the CLI endpoint
   (`health scan`) is built, as sketched in the research.
2. Keep the lookup in the plugin, or leave it to the agent?
3. Once the live check passes, extend the deploy script to install the plugin.
