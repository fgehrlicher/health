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
    ~/.local/bin/hermes -p food tools disable web browser code_execution image_gen tts \
      delegation cronjob computer_use connections >/dev/null 2>&1 || true
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
