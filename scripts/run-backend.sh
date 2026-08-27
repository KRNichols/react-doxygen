#!/bin/sh
# WHAT: Python lint and tests with a coverage floor.
# WHY: Auth, copy, signup, and docs handlers must stay green.
# WHO: make backend, pipeline.sh backend, hosted backend job.
# WHERE: backend Python and backend/tests
# HOW: Prefer the local virtualenv tools, then lint, then tests with coverage.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ -x "$ROOT/backend/.venv/bin/python" ]; then PY="$ROOT/backend/.venv/bin/python"; else PY=${PYTHON:-python3}; fi
if [ -x "$ROOT/backend/.venv/bin/ruff" ]; then RF="$ROOT/backend/.venv/bin/ruff"; else RF=${RUFF:-ruff}; fi
"$RF" check backend/*.py backend/scripts/*.py
COV="${COV_FAIL_UNDER:-70}"
(
  cd "$ROOT/backend"
  "$PY" -m pytest tests \
    --cov=app --cov=mock_okta --cov=signup_mail --cov=copy_text --cov=doxygen \
    --cov-report=term-missing --cov-fail-under="$COV"
)
