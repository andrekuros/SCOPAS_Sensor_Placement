#!/usr/bin/env bash
# Sync this package into Sensor-Placement-UTM (requires write access).
set -euo pipefail
DEST="${1:-../Sensor-Placement-UTM}"
SRC="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -d "$DEST/.git" ]]; then
  echo "Clone the paper repo first, e.g.:"
  echo "  git clone https://github.com/andrekuros/Sensor-Placement-UTM.git \"$DEST\""
  exit 1
fi
rsync -a \
  --exclude '.git' \
  --exclude 'SYNC_TO_UTM.sh' \
  "$SRC"/ "$DEST"/
echo "Synced $SRC -> $DEST"
echo "Next:"
echo "  cd \"$DEST\" && git checkout -b scopas-dual-layer-rerun"
echo "  git add -A && git commit -m 'SCOPAS dual-layer paper rerun' && git push -u origin HEAD"
