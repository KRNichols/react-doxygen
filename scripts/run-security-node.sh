#!/bin/sh
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PKG=npm
cd "$ROOT/frontend"
if [ -n "$CI" ] || [ ! -d node_modules ]; then
  "$PKG" ci --omit=dev
fi
"$PKG" audit --omit=dev --audit-level=high
