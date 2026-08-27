#!/bin/sh
# WHAT: JavaScript lint and unit tests.
# WHY: Keep a test fail distinct from a broken production bundle.
# WHO: make frontend, pipeline.sh frontend, hosted frontend job.
# WHERE: frontend/
# HOW: Fresh package install when CI is set or packages are missing, then lint and unit tests. No production bundle.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PKG=npm
cd "$ROOT/frontend"
if [ -n "$CI" ] || [ ! -d node_modules ]; then
  "$PKG" ci
fi
"$PKG" run lint
"$PKG" test
