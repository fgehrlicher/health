#!/usr/bin/env bash
# Copies the repository to health-box, rebuilds the production stack there, and
# installs the nightly backup timer. A deploy never touches the database volume,
# ~/health/.env or the dumps in ~/health-backups.
set -euo pipefail

cd "$(dirname "$0")/.."
HOST="${HEALTH_BOX:-fabian@192.168.178.161}"

rsync -az --delete --exclude-from=deploy/rsync-exclude.txt ./ "$HOST:health/"
ssh "$HOST" 'set -e
  cd health
  docker compose -f compose.prod.yaml up --detach --build --wait
  install -m 755 tools/health ~/.local/bin/health
  if [ -d ~/.hermes/profiles/food ]; then
    install -m 644 agents/food/SOUL.md ~/.hermes/profiles/food/SOUL.md
    mkdir -p ~/.hermes/profiles/food/skills/health/food-logging
    install -m 644 agents/food/skills/health/food-logging/SKILL.md \
      ~/.hermes/profiles/food/skills/health/food-logging/SKILL.md
    mkdir -p ~/.hermes/agent-hooks
    install -m 755 agents/food/hooks/terminal_guard.py ~/.hermes/agent-hooks/food-terminal-guard.py
    if ! grep -q "managed by deploy: food-terminal-guard" ~/.hermes/profiles/food/config.yaml; then
      cat agents/food/hooks/config-snippet.yaml >> ~/.hermes/profiles/food/config.yaml
    fi
    ~/.local/bin/hermes -p food tools disable web browser code_execution image_gen tts \
      delegation cronjob computer_use connections >/dev/null 2>&1 || true
  fi
  sudo install -m 644 deploy/health-backup.service deploy/health-backup.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now health-backup.timer >/dev/null
  systemctl list-timers health-backup.timer --no-pager | head -2'
