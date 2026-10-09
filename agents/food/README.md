# Food agent

The Hermes profile `food`: food and health logging, with its own Telegram bot.
The default profile stays the generic entry point.

Files here are copied to the server by `scripts/deploy-health-box.sh`:

- `SOUL.md` → `~/.hermes/profiles/food/SOUL.md`
- `skills/health/food-logging/SKILL.md` → the same path under the profile's `skills/`
- `tools/health` (the CLI, in the repository root) → `~/.local/bin/health`

Set-up on the server, once: the profile was created with
`hermes profile create food --clone` (logins and model copied from `default`),
bundled skills were removed, and `skills opt-out --remove` was run. The
Telegram token and the allowed user ID live only in
`~/.hermes/profiles/food/.env`.
