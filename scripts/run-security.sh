#!/bin/sh
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
sh "$ROOT/scripts/run-security-pip.sh"
sh "$ROOT/scripts/run-security-node.sh"
