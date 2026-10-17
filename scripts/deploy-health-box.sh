#!/usr/bin/env bash
# Copies the repository to health-box, rebuilds the production stack there, and
# installs the nightly backup timer. A deploy never touches the database volume,
# ~/health/.env or the dumps in ~/health-backups.
set -euo pipefail

cd "$(dirname "$0")/.."
HOST="${HEALTH_BOX:-fabian@192.168.178.161}"

# Hermes edits the food skills on the box; bring those edits into the repo first,
# or stop, so a deploy never overwrites them unseen.
scripts/sync-food-skills.sh

rsync -az --delete --exclude-from=deploy/rsync-exclude.txt ./ "$HOST:health/"
ssh "$HOST" 'set -e
  cd health
  docker compose -f compose.prod.yaml up --detach --build --wait
  install -m 755 tools/health ~/.local/bin/health
  if [ -d ~/.hermes/profiles/food ]; then
    install -m 644 agents/food/SOUL.md ~/.hermes/profiles/food/SOUL.md
    mkdir -p ~/.hermes/profiles/food/skills/health/food-logging
    cp -R agents/food/skills/health/food-logging/. ~/.hermes/profiles/food/skills/health/food-logging/
    mkdir -p ~/.hermes/agent-hooks
    install -m 755 agents/food/hooks/terminal_guard.py ~/.hermes/agent-hooks/food-terminal-guard.py
    if ! grep -q "managed by deploy: food-terminal-guard" ~/.hermes/profiles/food/config.yaml; then
      cat agents/food/hooks/config-snippet.yaml >> ~/.hermes/profiles/food/config.yaml
    fi
    if ! grep -q "managed by deploy: food-vision" ~/.hermes/profiles/food/config.yaml; then
      cat agents/food/vision-config-snippet.yaml >> ~/.hermes/profiles/food/config.yaml
    fi
    # The bot runs on the telegram platform; `tools disable` alone only narrows cli.
    # Without this, browser_exec runs any Python and gets past the terminal guard.
    for platform in cli telegram; do
      ~/.local/bin/hermes -p food tools disable --platform $platform web browser code_execution \
        image_gen tts delegation cronjob computer_use connections >/dev/null 2>&1 || true
    done
    toolsets=$(~/.local/bin/hermes -p food config get platform_toolsets.telegram 2>/dev/null)
    case "$toolsets" in
      *browser*|*code_execution*|*web*|*computer_use*|*delegation*|*cronjob*)
        echo "warning: the food bot still has tools outside the terminal guard: $toolsets" >&2;;
    esac
    # The agent has no clock (its terminal runs only `health`), so each of his messages
    # reaches it with the time he sent it, in Berlin time. config set keeps the comments.
    { ~/.local/bin/hermes -p food config set timezone Europe/Berlin \
        && ~/.local/bin/hermes -p food config set gateway.message_timestamps.enabled true; } >/dev/null 2>&1 \
      || echo "warning: could not turn on message timestamps; the food agent has no clock" >&2
    # The photo-scan plugin is repo code, replaced as a whole. Disabling and enabling
    # it makes the running gateway load the new code; no restart is needed.
    mkdir -p ~/.hermes/profiles/food/plugins
    rm -rf ~/.hermes/profiles/food/plugins/photo-scan
    cp -R agents/food/plugins/photo-scan ~/.hermes/profiles/food/plugins/photo-scan
    ~/.local/bin/hermes -p food plugins disable photo-scan >/dev/null 2>&1 || true
    ~/.local/bin/hermes -p food plugins enable photo-scan >/dev/null 2>&1 \
      || echo "warning: could not enable the photo-scan plugin; photos go to the agent unscanned" >&2
    # What the repo put on the box, so the next deploy can tell if Hermes has changed it.
    (cd ~/.hermes/profiles/food && find SOUL.md skills/health/food-logging -type f | LC_ALL=C sort | xargs sha256sum > .deployed-manifest)
  fi
  sudo install -m 644 deploy/health-backup.service deploy/health-backup.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now health-backup.timer >/dev/null
  systemctl list-timers health-backup.timer --no-pager | head -2'
