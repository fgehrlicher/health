#!/usr/bin/env bash
# Keeps the food agent's skill files in git when Hermes edits them on the box.
#
# Hermes changes its own skills: the background review after a conversation and
# the curator both rewrite SKILL.md and write references/ files on the box. A
# deploy must not overwrite those edits without anyone seeing them, so deploy
# runs this first. It compares the box with the state saved at the last deploy:
#
#   unchanged on the box                     nothing to do; the deploy goes ahead
#   changed, and already the same in the repo  the deploy goes ahead
#   changed, and already committed earlier   the deploy goes ahead: the edits are
#                                            kept in git, and the repo builds on
#                                            them (the saved state only catches
#                                            up at the next deploy)
#   changed, not in the repo                 the box's files are copied into the
#                                            repo and this stops (exit 2), so you
#                                            can review git diff and commit what
#                                            you keep, then deploy again
#   changed, and the repo has uncommitted edits too  stops (exit 1); nothing copied
#
#   scripts/sync-food-skills.sh
#
# Environment overrides:
#   HEALTH_BOX  SSH target (default fabian@192.168.178.161)
set -euo pipefail

cd "$(dirname "$0")/.."
HOST="${HEALTH_BOX:-fabian@192.168.178.161}"
PROFILE=".hermes/profiles/food"
PATHS=(SOUL.md skills/health/food-logging)  # the files deploy installs
MANIFEST=".deployed-manifest"               # saved on the box by deploy

ssh_box() {
  ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" "$@"
}

# Both sides sort the same way (byte order), so the manifests compare equal.
box_manifest() {
  ssh_box "cd ~/$PROFILE && find ${PATHS[*]} -type f | LC_ALL=C sort | xargs sha256sum"
}

repo_manifest() {
  (cd agents/food && find "${PATHS[@]}" -type f | LC_ALL=C sort | xargs shasum -a 256)
}

if ! ssh_box "test -d ~/$PROFILE"; then
  echo "No food profile on $HOST; nothing to sync."
  exit 0
fi

box=$(box_manifest)
saved=$(ssh_box "cat ~/$PROFILE/$MANIFEST 2>/dev/null || true")

if [ "$box" = "$saved" ]; then
  echo "Food skills on the box are unchanged since the last deploy."
  exit 0
fi

if [ "$box" = "$(repo_manifest)" ]; then
  echo "Food skills on the box already match the repo."
  exit 0
fi

# True when every file on the box is a version git already has for that path:
# Hermes's edits were synced and committed before, and the repo may have moved on.
box_edits_committed() {
  local copy file blob
  copy=$(mktemp -d)
  trap 'rm -rf "$copy"' RETURN
  mkdir -p "$copy/skills/health/food-logging"
  rsync -az "$HOST:$PROFILE/SOUL.md" "$copy/SOUL.md"
  rsync -az "$HOST:$PROFILE/skills/health/food-logging/" "$copy/skills/health/food-logging/"
  while IFS= read -r file; do
    blob=$(git hash-object "$copy/$file")
    git log --format=%H -- "agents/food/$file" \
      | while read -r commit; do git rev-parse -q --verify "$commit:agents/food/$file" || true; done \
      | grep -qx "$blob" || return 1
  done < <(cd "$copy" && find . -type f | sed 's|^\./||')
}

if box_edits_committed; then
  echo "Hermes's edits on the box are already committed in the repo."
  exit 0
fi

if [ -n "$(git status --porcelain -- agents/food/SOUL.md agents/food/skills/health/food-logging)" ]; then
  echo "The food skills changed on the box, and the repo has uncommitted edits to the same files." >&2
  echo "Commit or stash those edits, then run this again. Nothing was copied." >&2
  exit 1
fi

# Copies only; nothing on the box is removed. Files the repo has but the box lacks stay.
rsync -az "$HOST:$PROFILE/SOUL.md" agents/food/SOUL.md
rsync -az "$HOST:$PROFILE/skills/health/food-logging/" agents/food/skills/health/food-logging/

echo "Copied the food skills from the box into the repo. Changes to review:"
git --no-pager diff --stat -- agents/food/SOUL.md agents/food/skills/health/food-logging
git status --short -- agents/food/SOUL.md agents/food/skills/health/food-logging
echo "Review with git diff, commit what you keep, then run the deploy again."
exit 2
