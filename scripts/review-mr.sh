#!/bin/sh
# WHAT: Thin wrapper that starts the GitLab MR reviewer helper.
# WHY: make review and the GitLab job must share one entry so they cannot drift.
# WHO: make review and the GitLab review job on merge_request_event.
# WHERE: scripts/review-mr.sh at the repository root.
# HOW: cd to the repo root and exec backend/scripts/review_mr.py with python3.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/backend/.venv/bin/python" ] && [ -z "$PYTHON_SET" ]; then
  if [ "$PYTHON" = "python3" ]; then
    PYTHON="$ROOT/backend/.venv/bin/python"
  fi
fi
exec "$PYTHON" "$ROOT/backend/scripts/review_mr.py" "$@"
