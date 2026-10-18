# Food agent

The Hermes profile `food`: food and health logging, with its own Telegram bot.
The default profile stays the generic entry point.

Files here are copied to the server by `scripts/deploy-health-box.sh`:

- `SOUL.md` → `~/.hermes/profiles/food/SOUL.md`
- `skills/health/food-logging/SKILL.md` → the same path under the profile's `skills/`
- `tools/health` (the CLI, in the repository root) → `~/.local/bin/health`
- `hooks/terminal_guard.py` → `~/.hermes/agent-hooks/food-terminal-guard.py`: lets
  the terminal run only plain `health` commands. `hooks/config-snippet.yaml`
  registers it and is appended once to the profile's `config.yaml`.
- `vision-config-snippet.yaml`: appended once to the profile's `config.yaml`, so
  photos are described by Opus.
- Toolsets, narrowed on every deploy for both platforms, `cli` and `telegram`
  (the bot runs on `telegram`): no web, browser, code execution, image, speech,
  delegation, cron, computer-use or connection tools. The deploy warns if the
  `telegram` set still holds one, since `browser_exec` would get past the
  terminal guard.
- `timezone: Europe/Berlin` and `gateway.message_timestamps.enabled: true`, set in
  the profile's `config.yaml` with `hermes config set` on every deploy: each of his
  messages reaches the agent with the time he sent it. The agent has no other
  clock, since its terminal runs only `health`.
- `plugins/photo-scan/` → `~/.hermes/profiles/food/plugins/photo-scan/`: decodes
  barcodes and QR codes in each incoming photo through the API and adds them to
  the message ([Scan tool](../../docs/scan-tool.md)). Replaced on every deploy,
  then disabled and enabled so the running gateway loads the new code.

Hermes edits `SOUL.md` and the skill on the box. Before copying, the deploy runs
`scripts/sync-food-skills.sh`, which brings such edits into the repository and
stops, so they can be reviewed and committed instead of being overwritten.

Set-up on the server, once: the profile was created with
`hermes profile create food --clone` (logins and model copied from `default`),
bundled skills were removed, and `skills opt-out --remove` was run. The
Telegram token and the allowed user ID live only in
`~/.hermes/profiles/food/.env`.
