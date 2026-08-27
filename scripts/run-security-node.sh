#!/bin/sh
# WHAT: Production Node advisory scan.
# WHY: The shipped UI must not depend on a high-severity package.
# WHO: make security-node, pipeline.sh security-node, hosted node-audit job.
# WHERE: frontend production tree
# HOW: Fresh production install when CI is set or packages are missing, then high-severity audit.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
PKG=npm
cd "$ROOT/frontend"
if [ -n "$CI" ] || [ ! -d node_modules ]; then
  "$PKG" ci --omit=dev
fi
"$PKG" audit --omit=dev --audit-level=high
