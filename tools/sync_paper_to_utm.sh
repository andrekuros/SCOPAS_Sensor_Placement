#!/usr/bin/env bash
# Sync SCOPAS paper_utm/ → https://github.com/andrekuros/Sensor-Placement-UTM
#
# Usage (from SCOPAS repo root):
#   ./tools/sync_paper_to_utm.sh
#   ./tools/sync_paper_to_utm.sh --dry-run
#   ./tools/sync_paper_to_utm.sh --no-push
#   ./tools/sync_paper_to_utm.sh --dest ~/code/Sensor-Placement-UTM
#   ./tools/sync_paper_to_utm.sh --branch scopas-paper-sync
#
# Requires: git, rsync, and write access to Sensor-Placement-UTM (your GitHub creds).

set -euo pipefail

REPO_URL="${UTM_PAPER_REPO_URL:-https://github.com/andrekuros/Sensor-Placement-UTM.git}"
BRANCH="${UTM_PAPER_BRANCH:-main}"
DEST=""
DRY_RUN=0
DO_PUSH=1
COMMIT_MSG=""
ALLOW_DIRTY_SRC=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCOPAS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$SCOPAS_ROOT/paper_utm"

usage() {
  cat <<'EOF'
Sync SCOPAS paper_utm/ → https://github.com/andrekuros/Sensor-Placement-UTM

Usage (from SCOPAS repo root):
  ./tools/sync_paper_to_utm.sh
  ./tools/sync_paper_to_utm.sh --dry-run
  ./tools/sync_paper_to_utm.sh --no-push
  ./tools/sync_paper_to_utm.sh --dest ~/code/Sensor-Placement-UTM
  ./tools/sync_paper_to_utm.sh --branch scopas-paper-sync

Requires: git, and write access to Sensor-Placement-UTM (your GitHub creds).
Uses rsync when available; otherwise falls back to Python copy.
EOF
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-push) DO_PUSH=0; shift ;;
    --dest) DEST="${2:?}"; shift 2 ;;
    --branch) BRANCH="${2:?}"; shift 2 ;;
    --repo) REPO_URL="${2:?}"; shift 2 ;;
    --message|-m) COMMIT_MSG="${2:?}"; shift 2 ;;
    --allow-dirty-src) ALLOW_DIRTY_SRC=1; shift ;;
    *)
      echo "Unknown option: $1" >&2
      usage 1
      ;;
  esac
done

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: paper package not found at $SRC" >&2
  exit 1
fi
if [[ ! -f "$SRC/main.tex" ]]; then
  echo "ERROR: $SRC/main.tex missing — refusing to sync" >&2
  exit 1
fi

# Default clone location: sibling of SCOPAS, or cache under /tmp
if [[ -z "$DEST" ]]; then
  sibling="$(cd "$SCOPAS_ROOT/.." && pwd)/Sensor-Placement-UTM"
  if [[ -d "$sibling/.git" ]]; then
    DEST="$sibling"
  else
    DEST="${XDG_CACHE_HOME:-$HOME/.cache}/scopas-utm-paper/Sensor-Placement-UTM"
  fi
fi

echo "==> Source : $SRC"
echo "==> Dest   : $DEST"
echo "==> Branch : $BRANCH"
echo "==> Remote : $REPO_URL"

if [[ ! -d "$DEST/.git" ]]; then
  echo "==> Cloning $REPO_URL → $DEST"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    (dry-run: would clone)"
  else
    mkdir -p "$(dirname "$DEST")"
    git clone "$REPO_URL" "$DEST"
  fi
else
  echo "==> Using existing clone"
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  git -C "$DEST" fetch origin
  # Prefer requested branch; create from default remote HEAD if missing
  if git -C "$DEST" show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
    git -C "$DEST" checkout "$BRANCH"
    git -C "$DEST" pull --ff-only origin "$BRANCH" || true
  elif git -C "$DEST" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git -C "$DEST" checkout "$BRANCH"
  else
    default_ref="$(git -C "$DEST" symbolic-ref -q refs/remotes/origin/HEAD 2>/dev/null || true)"
    default_branch="${default_ref##*/}"
    [[ -n "$default_branch" ]] || default_branch="main"
    echo "==> Branch '$BRANCH' missing; creating from origin/$default_branch"
    git -C "$DEST" checkout -B "$BRANCH" "origin/$default_branch"
  fi
fi

RSYNC_EXCLUDES=(
  --exclude '.git/'
  --exclude 'SYNC_TO_UTM.sh'
  --exclude '.DS_Store'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '.overleaf'
)

echo "==> Syncing paper_utm/ → paper repo root"

sync_with_python() {
  local dry="$1"
  python3 - "$SRC" "$DEST" "$dry" <<'PY'
import os, sys, shutil
from pathlib import Path
src, dest, dry = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] == "1"
exclude_names = {".git", "SYNC_TO_UTM.sh", ".DS_Store", "__pycache__", ".overleaf"}
exclude_suffixes = {".pyc"}

def ignored(path: Path) -> bool:
    return path.name in exclude_names or path.suffix in exclude_suffixes

# Collect source files relative to src
files = []
for root, dirs, names in os.walk(src):
    root_p = Path(root)
    dirs[:] = [d for d in dirs if d not in exclude_names]
    for name in names:
        p = root_p / name
        if ignored(p):
            continue
        rel = p.relative_to(src)
        files.append(rel)

wanted = set(files)
# Delete dest files not in source (except .git and sync marker handled separately)
if dest.exists():
    for root, dirs, names in os.walk(dest):
        root_p = Path(root)
        if ".git" in root_p.parts:
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            p = root_p / name
            if p.name == ".scopas_paper_sync":
                continue
            rel = p.relative_to(dest)
            if rel not in wanted:
                print(f"delete {rel}")
                if dry != "1":
                    p.unlink()

for rel in sorted(wanted):
    s, d = src / rel, dest / rel
    print(f"copy   {rel}")
    if dry != "1":
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
PY
}

if command -v rsync >/dev/null 2>&1; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    rsync -a --dry-run --delete --itemize-changes "${RSYNC_EXCLUDES[@]}" "$SRC"/ "$DEST"/ || true
    echo "(dry-run complete — no commit/push)"
    exit 0
  fi
  # DEST must exist for rsync trailing-slash semantics when clone was skipped in dry-run paths
  mkdir -p "$DEST"
  rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$SRC"/ "$DEST"/
else
  echo "    (rsync not found — using Python fallback)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    mkdir -p "$DEST"
    sync_with_python 1
    echo "(dry-run complete — no commit/push)"
    exit 0
  fi
  mkdir -p "$DEST"
  sync_with_python 0
fi

# Record provenance for Overleaf / future syncs
{
  echo "source_repo: andrekuros/SCOPAS_Sensor_Placement"
  echo "source_path: paper_utm/"
  echo "source_commit: $(git -C "$SCOPAS_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "source_branch: $(git -C "$SCOPAS_ROOT" branch --show-current 2>/dev/null || echo unknown)"
  echo "synced_at_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$DEST/.scopas_paper_sync"

cd "$DEST"
git add -A

if git diff --cached --quiet; then
  echo "==> No paper changes to commit (already up to date)."
  exit 0
fi

if [[ -z "$COMMIT_MSG" ]]; then
  src_short="$(git -C "$SCOPAS_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  COMMIT_MSG="Sync paper from SCOPAS paper_utm (@$src_short)"
fi

git commit -m "$COMMIT_MSG"
echo "==> Committed: $COMMIT_MSG"

if [[ "$DO_PUSH" -eq 1 ]]; then
  echo "==> Pushing to origin/$BRANCH"
  git push -u origin "$BRANCH"
  echo "==> Done. Overleaf: pull / re-import from $REPO_URL (branch $BRANCH)"
else
  echo "==> Skipped push (--no-push). Review in $DEST then:"
  echo "    git -C \"$DEST\" push -u origin $BRANCH"
fi
