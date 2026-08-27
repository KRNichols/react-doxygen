#!/bin/sh
# WHAT: Local quality slices: lint, comments, unused code, and the fast check.
# WHY: Hosted jobs and make targets must call one script so the gates match.
# WHO: make check/lint/comments/deadcode/quality and pipeline.sh.
# WHERE: scripts/check.sh from the repo root.
# HOW: Prefer the local virtualenv tools. Named slices: lint, comments, deadcode, packages.
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
# WHAT: Language lint for Python and, when present, JavaScript.
# WHY: Style errors should fail before tests run.
# WHO: make lint and the check slice.
# WHERE: backend Python and frontend JS.
# HOW: ruff on backend. eslint on frontend when the binary exists; otherwise say so.
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
# WHAT: Five-part comment inventory on the whole first-party tree.
# WHY: A docs-only change is not a comment upgrade; --all must still be green.
# WHO: make comments and make quality.
# WHERE: backend/scripts/check_comments.py
# HOW: Always pass --all so the gate does not shrink to a delta.
comments() {
  "$PYTHON" backend/scripts/check_comments.py --all
}
# WHAT: Unused import and unused variable scan.
# WHY: Dead names should not land just because tests still pass.
# WHO: make deadcode and make quality.
# WHERE: backend Python.
# HOW: ruff rules F401 and F841 only.
deadcode() {
  "$RUFF" check --select F401,F841 backend/*.py backend/scripts/*.py
}
# WHAT: Fail when a declared package is not on the repo allowlist.
# WHY: A new first-party dependency must not land without an allowlist edit.
# WHO: make packages, make check, make quality, make ci.
# WHERE: backend/scripts/check_packages.py against approved-packages.json.
# HOW: Run the checker with the same PYTHON as the other quality slices.
packages() {
  "$PYTHON" backend/scripts/check_packages.py
}
case "$target" in
  lint) lint ;;
  comments) comments ;;
  deadcode) deadcode ;;
  packages) packages ;;
  check) lint && comments && packages ;;
  ci) sh "$ROOT/scripts/pipeline.sh" ci ;;
  *) echo "usage: $0 [check|lint|comments|deadcode|packages|ci]" >&2; exit 2 ;;
esac
