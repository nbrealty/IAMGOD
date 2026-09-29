#!/usr/bin/env bash
# Load or save the trading state (positions, equity history, journals, pending decision files).
#
#   scripts/state.sh pull   # before a run: fetch the `trading-state` branch into the state folder
#   scripts/state.sh push   # after a run: commit the state folder and push it to `trading-state`
#
# The state folder is $TRADER_STATE_DIR (default: trading/state). It is its own small git repository
# on the `trading-state` branch, the same pattern as .github/workflows/paper-trading.yml.
# This script only ever runs git inside the state folder; it never touches the code branch.
#
# Optional: STATE_REPO_URL (default: the code repository's `origin` URL), STATE_BRANCH (default trading-state).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRADING="$(cd "$HERE/.." && pwd)"
DIR="${TRADER_STATE_DIR:-$TRADING/state}"
BRANCH="${STATE_BRANCH:-trading-state}"

die() { echo "state.sh: $*" >&2; exit 1; }

repo_url() {
  if [ -n "${STATE_REPO_URL:-}" ]; then
    echo "$STATE_REPO_URL"
  else
    git -C "$TRADING" remote get-url origin 2>/dev/null \
      || die "no STATE_REPO_URL and the code repository has no 'origin' remote"
  fi
}

# True only when $DIR is the top of its own git repository (not a folder inside the code repository).
own_repo() {
  [ -e "$DIR/.git" ] || return 1
  local top
  top="$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null)" || return 1
  [ "$(cd "$top" && pwd -P)" = "$(cd "$DIR" && pwd -P)" ]
}

ignore_cache() {
  # Backtest caches are large and rebuilt on demand; .gitkeep belongs to the code repository.
  local line
  for line in 'cache/' '.gitkeep'; do
    grep -qxF "$line" "$DIR/.gitignore" 2>/dev/null || echo "$line" >> "$DIR/.gitignore"
  done
}

# Does the state remote have the branch? `ls-remote --exit-code` exits 2 only when the branch is missing; any
# other failure (network, auth, bad URL) must stop the session, never read as "no saved state yet": the books
# would then start with no lots while the paper account holds positions.
remote_has_branch() {
  local rc=0
  git -C "$DIR" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) return 0 ;;
    2) return 1 ;;
    *) die "could not reach the state remote (git ls-remote exit $rc: network or auth failure). Do not run the books; stop and tell the owner." ;;
  esac
}

pull() {
  mkdir -p "$DIR"
  if own_repo; then
    local current
    current="$(git -C "$DIR" symbolic-ref --short -q HEAD || true)"
    [ "$current" = "$BRANCH" ] || die "$DIR is on branch '$current', expected '$BRANCH'"
    if remote_has_branch; then
      git -C "$DIR" pull --quiet --ff-only origin "$BRANCH" \
        || die "could not fast-forward $DIR to origin/$BRANCH (local state has commits the remote lacks, or conflicts). Stop and tell the owner."
      echo "state: updated $DIR from $BRANCH ($(git -C "$DIR" log -1 --format='%h %s'))"
    else
      echo "state: $BRANCH does not exist on the remote yet; keeping the local state in $DIR"
    fi
    ignore_cache
    return 0
  fi

  [ -e "$DIR/.git" ] && die "$DIR/.git exists but is not a repository of its own; move it aside first"
  local url
  url="$(repo_url)"
  git -C "$DIR" init --quiet
  git -C "$DIR" symbolic-ref HEAD "refs/heads/$BRANCH"
  git -C "$DIR" remote add origin "$url"
  own_repo || die "could not create a separate git repository in $DIR"
  if remote_has_branch; then
    git -C "$DIR" fetch --quiet origin "$BRANCH" || die "could not fetch $BRANCH from the remote"
    # Files already in the folder that the branch also has would be overwritten: refuse instead.
    git -C "$DIR" checkout --quiet -b "$BRANCH" FETCH_HEAD \
      || die "files in $DIR clash with the saved state on $BRANCH; move them aside and pull again"
    git -C "$DIR" branch --quiet --set-upstream-to="origin/$BRANCH" "$BRANCH" 2>/dev/null \
      || git -C "$DIR" config "branch.$BRANCH.remote" origin
    echo "state: loaded $BRANCH into $DIR ($(git -C "$DIR" log -1 --format='%h %s'))"
  else
    echo "state: $BRANCH does not exist on the remote yet; starting with an empty state in $DIR"
  fi
  ignore_cache
}

# The newest run date saved in the books' state files (the market date, not the wall clock); else today (UTC).
run_date() {
  local d
  d="$(cat "$DIR"/*/state.json 2>/dev/null \
       | grep -oE '"last_run_date": *"[0-9]{4}-[0-9]{2}-[0-9]{2}"' | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' \
       | sort | tail -n 1 || true)"
  echo "${d:-$(date -u +%F)}"
}

push() {
  own_repo || die "$DIR is not a state repository; run 'scripts/state.sh pull' first"
  local current
  current="$(git -C "$DIR" symbolic-ref --short -q HEAD || true)"
  [ "$current" = "$BRANCH" ] || die "$DIR is on branch '$current', expected '$BRANCH'"
  ignore_cache
  git -C "$DIR" config user.name >/dev/null || git -C "$DIR" config user.name "paper-trading-bot"
  git -C "$DIR" config user.email >/dev/null \
    || git -C "$DIR" config user.email "paper-trading-bot@users.noreply.github.com"
  git -C "$DIR" add -A
  if git -C "$DIR" diff --cached --quiet; then
    echo "state: nothing changed since the last save"
  else
    git -C "$DIR" commit --quiet -m "State after run on $(run_date)"
  fi
  if ! git -C "$DIR" rev-parse --verify --quiet HEAD >/dev/null; then
    echo "state: nothing to push yet"
    return 0
  fi
  git -C "$DIR" push --quiet origin "HEAD:refs/heads/$BRANCH" \
    || die "could not push $BRANCH. The state is saved only in $DIR on this machine. Tell the owner."
  echo "state: pushed $BRANCH ($(git -C "$DIR" log -1 --format='%h %s'))"
}

case "${1:-}" in
  pull) pull ;;
  push) push ;;
  *) echo "usage: $0 pull|push   (state folder: \$TRADER_STATE_DIR, default trading/state)" >&2; exit 2 ;;
esac
