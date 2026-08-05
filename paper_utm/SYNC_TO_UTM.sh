#!/usr/bin/env bash
# Thin wrapper kept next to the paper package.
# Prefer:  ./tools/sync_paper_to_utm.sh
exec "$(cd "$(dirname "$0")/.." && pwd)/tools/sync_paper_to_utm.sh" "$@"
