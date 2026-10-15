# Backlog

Planned work that is not built yet, in the order we agreed. Items 1 to 2 of the
October 2026 feedback round (stats cleanup with the 300 kcal tolerance, and
stated items without a product) are done and not listed here.

## Next

1. **Scan tool for barcodes and QR codes.** A `health scan <photo>` command decodes
   EAN/UPC and QR codes deterministically (zbar), checks the check digit, and passes
   the code to the existing barcode lookup. The model should not read digits from
   photos. QR codes on packaging are usually links: decode them and show the URL, but
   never open it.

2. **Branded food lookup on demand.** Open Food Facts is the first candidate (EAN
   lookup, free API, good German coverage). The lookup is read-only and returns
   candidates. Registration still needs the user's confirmation. Open Food Facts data
   is ODbL, so attribution is required, and the same plausibility checks apply as to
   label values.

3. **Voice memos.** The gap is speech-to-text, because Telegram sends OGG audio. The
   user accepts a cloud model (Claude or Codex); his machine is too weak for a local
   one. Store the transcript as the meal note, not the audio. First verify that Hermes
   passes voice messages to a tool at all.

4. **Dates in Telegram ("What is today?", "What was yesterday?").** Fix by structure,
   not by prompt wording: inject the current Berlin date and time into every Telegram
   turn, and let the CLI resolve "today" and "yesterday" on the server. Depends on
   whether Hermes supports per-turn context.

5. **Health evaluation.** A module inside the existing API, not a second service (one
   database). A profile table (sex, age, height, activity, goal). Protein targets per
   kg of body weight: the DGE reference is about 0.8 g/kg for the general population,
   and the ISSN position stand is roughly 1.4 to 2.0 g/kg per day for people who train
   (verify before relying on it). A guidelines table where every benchmark has a
   source, year and quote. The agent may say "sodium was above the reference on 9 of
   14 days", but never diagnose. Deficiencies need blood work, not a food log.

6. **Agent memory.** Health facts (goals, profile, preferences about logging) belong in
   the database, not in agent memory. Agent memory keeps conversation style and open
   threads. Choose a Hermes memory add-on only after deciding what must be remembered.

7. **The general agent changing the health app.** The riskiest item, so last.
   Guardrails: work on a branch and open a pull request, never push to `main`;
   `make check` and `make check-e2e` must pass; deploy only after the user approves in
   Telegram; back up before every deploy (`scripts/backup-db.sh` exists); migrations
   always need explicit approval; its credentials can run only the deploy script, with
   no general sudo. Start read-only: it reads the code and proposes a diff, and the
   user applies it.

8. **Architecture.** Keep one API and one database, the `health` CLI as the agent's
   only door, and the web app. Split features into domain modules inside the API.
   Move rules that can be validations out of the skill text and into the API. Hermes
   once overwrote the stated-item rules on the box, so rules that live only in prose
   are fragile.

## Small follow-ups

- Add stated items from the web meal sheet. Today the agent can log them, and the web
  app shows and keeps them, but it cannot create them.
- Restore the kcal total on Today if wanted. It was removed on purpose: Today shows
  only protein, fat, carbs and fiber. Each meal still shows its kcal.
- `pnpm test` (vitest) fails because it also collects the Playwright specs in `e2e/`.
  Exclude `e2e/` in a vitest config.
- The test database is shared. Run `make test-db` before `make check` after an e2e
  run, or the catalog and recipe tests can see leftover e2e data.

## Decided, not planned

- **Weight tracking:** left out. Apple Health already covers weight.
- **Stated items:** values come from the user only. A rough figure is flagged as
  estimated. The agent never adds numbers from its own knowledge of a food.
