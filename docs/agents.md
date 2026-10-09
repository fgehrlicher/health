# Agents: how Hermes connects to the apps

Status: **concept, partly built.** The CLI (`tools/health`) and the food agent's files
(`agents/food/`) exist; the Telegram bot for the food agent is the next step.

## Principles

- **An agent is a Hermes profile.** Each has one purpose, its own bot, memory,
  skills, toolsets and model settings. Adding a use case means adding a profile;
  the others don't change.
- **Apps expose a CLI, agents call it.** The app owns the rules (validation,
  nutrition math, what counts as estimated). The agent owns the judgement
  (what to ask, how to read a photo, what to confirm).
- **Shared tools, separate knowledge.** Several agents can use the same CLI.
  Their memories and skills stay separate.

## Interface: CLI first, MCP later

**Recommendation: a plain command-line tool, not an MCP server.** Reasons:

- Hermes already runs shell commands, so the agent can call a CLI without any
  extra server, container or open port.
- The same CLI works for you, for the deploy and backup scripts, and for tests.
  An MCP server works only for agents.
- Access is controlled per profile through toolsets. A restaurant agent never
  gets the health commands.
- Inputs and outputs are plain JSON, which is easy to test and to log.

What MCP would add: typed tool schemas and discovery. That matters when many
clients on several machines need the same tools. Neither is true yet. If it
becomes true, the CLI can be wrapped as an MCP server without changing the app.

**The CLI** (`health`, one file, standard library only, so it needs no install):

- Talks to the API on `127.0.0.1:8000`. It holds no rules of its own.
- JSON output on every command, which the agent reads directly.
- Complex writes take a JSON file, so no shell quoting is needed.
- Writes are dry-run by default: `health meal log --file meal.json` prints what
  would be stored; `--commit` stores it.
- Exit codes: `0` ok, `2` validation issue (the API's field messages on stdout),
  `3` not found, `4` the API is unavailable.

| Command | Purpose |
| --- | --- |
| `health foods search <query>` | catalog foods, German and English names |
| `health foods get <slug>` | nutrition, portions, label gaps |
| `health foods barcode <code>` | a scanned product |
| `health product check --file p.json` | validate a label (dry run) |
| `health product register --file p.json --commit` | save a validated product |
| `health meal log --file m.json [--commit]` | log foods, portions and cooks |
| `health day <YYYY-MM-DD>` | what was eaten, with totals |
| `health recipes list [--tag T]`, `health recipes get <slug>` | recipes |
| `health cook log --file c.json [--commit]` | record a cook |

The first version has no delete command, and no way to change a registered
product's nutrition.

## Profiles: the scalability model

**Layout.** Each agent is a folder, kept in its own repository or in
`homelab/agents/`:

```
agents/health/
  distribution.yaml   name, description, version
  SOUL.md             role, language, reply style
  config.yaml         model settings and toolsets
  skills/health/…     the skills for this agent
```

**Installed per machine, never in the folder:** the bot token and the allowed
Telegram user IDs (`.env`), memories and sessions. The Hermes docs say the same:
credentials, memories and sessions stay on the machine.

**Installing:** `hermes profile install <folder-or-git-url>`. The CLI accepts a
local folder with a `distribution.yaml`; the docs only describe git. Updates for
a local folder need checking before we rely on them.

**Adding a use case:**

1. Create a bot in BotFather (see the Telegram docs).
2. Put the agent's folder in place and install it as a profile.
3. Write the bot token and your user ID into that profile's `.env`.
4. Start the gateway and send a test message.

**What is shared and what is not.** The `health` CLI is shared, installed once on
the server. Profiles don't share memory or skills. If two agents must share
knowledge, copy the shared skill into both profiles, or use an external memory
provider (the Hermes docs recommend this rather than two agents writing one
memory).

**Planned profiles:**

| Profile | Purpose | Tools |
| --- | --- | --- |
| `default` (health) | food logging, goals, recipes | the `health` CLI, vision |
| `food-research` (later) | restaurant and food-spot research for you and your partner | web tools only; no health access |

The second profile is not built in this phase. It is in the table to show that
the structure takes it without changes.

## Models

- **Main model per profile: Haiku 5.5.** Chat, tool calls and routing.
- **Vision: Opus 5.** Hermes has a per-task setting for vision
  (`auxiliary.vision`, with its own `provider` and `model`). This keeps photos on
  the stronger model and everyday messages on Haiku.
- **Caveat to test first.** The config comments say that providers other than
  OpenRouter and Nous Portal are experimental for these tasks. We test Opus over
  the direct Anthropic provider first. If that fails, the route is OpenRouter,
  which needs its own API key.
- **Cost.** Each photo sent to Opus costs more than a text message. The agent
  should ask before reading many photos at once.

## Routing: how a message reaches an agent

**A. One bot per agent (recommended now).** Each agent has its own bot in
Telegram. You write to the bot you want. Routing is deterministic and costs
nothing. It scales to any number of agents, at the price of several bots in
your chat list.

**B. A front-door agent (later, after a test).** A small, cheap agent receives
free-text messages and creates kanban tasks for specialist profiles, based on
the profile descriptions. Kanban is shared across profiles, and `/kanban` works
from Telegram. The docs don't say whether ordinary free-text messages create
tasks, so this needs a spike before we depend on it. It adds a model call and
some latency to every message.

**C. Chat routing (fallback).** Each agent gets its own Telegram group, and the
gateway routes by chat ID. The gateway's `profile_routes` setting does this. It
works, but it means maintaining groups.

Our recommendation is A now, and B only once there are three or more agents and
a test shows it works.

## Safety of agent access

- **Only the CLI reaches the API.** The food profile's terminal may run plain
  `health` commands. A pre-tool hook (`agents/food/hooks/terminal_guard.py`)
  blocks everything else: curl, Python, URLs, pipes, redirects and chains.
  It fails closed.
- **Toolsets are narrowed per profile.** The food profile has no web, browser,
  code execution, desktop, cron or delegation tools.
- **No deletes or edits from chat.** The CLI has no such command, and the
  persona and skill say so. Changes go through the web app.
- **Known gap:** the default profile still has an unguarded terminal, so it can
  call the API directly. Give it the same kind of guard, or narrow it, before
  it is given health tools.
- **Model behaviour is not guaranteed.** The rules tell the agent not to narrate
  its steps, and the first test followed them. Keep checking real replies.

## Phases

1. **Health agent through the CLI.** Build the CLI, set up the profile from a
   folder, and test with about ten real messages: a plate photo, a barcode, an
   unknown food, a recipe portion, "what did I eat yesterday", an unclear time.
2. **Vision on Opus.** Test the Opus route for photos before the health agent
   relies on it.
3. **Multi-agent layout.** Put the folder structure and the add-a-profile steps
   in place, so the second agent is a routine change.
4. **Second use case** (restaurant research), when you decide to start it.
5. **Front-door routing** (option B), only if three or more agents make bots
   impractical.

## Decisions needed

- **CLI over MCP:** agreed?
- **One bot per agent (option A):** agreed?
- **Opus for vision:** test over the direct Anthropic provider, falling back to
  OpenRouter, which needs a key. Which do you prefer if the direct route fails?
- **Where the agent folders live:** in the homelab repository, or in their own
  repository per agent?
- **Reply language, writes policy, goals:** still open from before. For writes,
  the CLI's dry-run default means the agent shows what it will store, and you
  confirm before `--commit`.
