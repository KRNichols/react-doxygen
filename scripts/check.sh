#!/bin/sh
# WHAT: Local quality slices: lint, comments, unused code, and the fast check.
# WHY: Hosted jobs and make targets must call one script so the gates match.
# WHO: make check/lint/comments/deadcode/quality and pipeline.sh.
# WHERE: scripts/check.sh from the repo root.
# HOW: Prefer the local virtualenv tools. Each named slice is a function below.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
PYTHON="${PYTHON:-backend/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON=python3
fi
RUFF="${RUFF:-backend/.venv/bin/ruff}"
if [ ! -x "$RUFF" ]; then
  RUFF=ruff
fi
target=${1:-check}
lint() {
  "$RUFF" check backend/*.py backend/scripts/*.py
  if [ -x frontend/node_modules/.bin/eslint ]; then
    (cd frontend && ./node_modules/.bin/eslint src)
  elif command -v eslint >/dev/null 2>&1; then
    eslint --no-eslintrc --env es6 --env browser --parser-options=ecmaVersion:2022,sourceType:module frontend/src/api.js frontend/src/docsParse.js
  else
    echo "eslint not installed; JS lint runs in the frontend gate"
  fi
}
comments() {
  "$PYTHON" backend/scripts/check_comments.py --all
}
deadcode() {
  "$RUFF" check --select F401,F841 backend/*.py backend/scripts/*.py
}
case "$target" in
  lint) lint ;;
  comments) comments ;;
  deadcode) deadcode ;;
  check) lint && comments ;;
  ci) sh "$ROOT/scripts/pipeline.sh" ci ;;
  *) echo "usage: $0 [check|lint|comments|deadcode|ci]" >&2; exit 2 ;;
esac
