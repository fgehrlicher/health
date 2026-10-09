#!/usr/bin/env bash
# Dumps the production database to ~/health-backups and deletes dumps older than
# KEEP_DAYS. Runs on the server (see deploy/health-backup.timer). Dumps stay on
# the server; nothing is copied off the machine.
set -euo pipefail

cd "$(dirname "$0")/.."
DEST="${HEALTH_BACKUP_DIR:-$HOME/health-backups}"
KEEP_DAYS="${HEALTH_BACKUP_KEEP_DAYS:-14}"
COMPOSE=(docker compose -f compose.prod.yaml)

mkdir -p "$DEST"
stamp="$(date +%Y%m%d-%H%M%S)"
partial="$DEST/.health-$stamp.dump.partial"
final="$DEST/health-$stamp.dump"

"${COMPOSE[@]}" exec -T postgres pg_dump --username=health --dbname=health --format=custom > "$partial"
# A dump that cannot be listed is not a backup: refuse to keep it.
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "$partial" > /dev/null
mv "$partial" "$final"

find "$DEST" -maxdepth 1 -name 'health-*.dump' -mtime +"$KEEP_DAYS" -delete
echo "$final"
