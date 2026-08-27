#!/bin/sh
# WHAT: Python package advisory scan.
# WHY: The API stack must not ship a known-bad wheel.
# WHO: make security-pip, pipeline.sh security-pip, hosted pip-audit job.
# WHERE: backend/requirements.txt
# HOW: Prefer the local virtualenv interpreter, then the auditor on the requirements file.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ -x "$ROOT/backend/.venv/bin/python" ]; then PY="$ROOT/backend/.venv/bin/python"; else PY=${PYTHON:-python3}; fi
"$PY" -m pip_audit -r backend/requirements.txt
