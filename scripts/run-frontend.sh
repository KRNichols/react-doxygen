#!/bin/sh
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PKG=npm
cd "$ROOT/frontend"
if [ -n "$CI" ] || [ ! -d node_modules ]; then
  if [ -f package-lock.json ]; then
    "$PKG" ci
  else
    "$PKG" install
  fi
fi
"$PKG" run lint
"$PKG" test
"$PKG" run build
