#!/bin/sh
# WHAT: Python and Node advisory scans together.
# WHY: Local twin of the hosted security workflow.
# WHO: make security and pipeline.sh security.
# WHERE: The two security runner scripts.
# HOW: Python requirements scan, then production Node high-severity scan.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
sh "$ROOT/scripts/run-security-pip.sh"
sh "$ROOT/scripts/run-security-node.sh"
