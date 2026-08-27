#!/bin/sh
# WHAT: Production frontend bundle.
# WHY: Flask serves the built files on port 5000.
# WHO: make build, pipeline.sh build, hosted build job.
# WHERE: frontend/
# HOW: Fresh package install when CI is set or packages are missing, then the production bundler.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PKG=npm
cd "$ROOT/frontend"
if [ -n "$CI" ] || [ ! -d node_modules ]; then
  "$PKG" ci
fi
"$PKG" run build
