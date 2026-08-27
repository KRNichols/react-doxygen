#!/bin/sh
# Portable contract for GitHub Actions and GitLab CI.
set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
slice=${1:-ci}
if [ "$slice" = all ]; then slice=ci; fi
case "$slice" in
  lint) sh scripts/check.sh lint ;;
  comments) sh scripts/check.sh comments ;;
  deadcode) sh scripts/check.sh deadcode ;;
  quality) sh scripts/check.sh lint; sh scripts/check.sh comments; sh scripts/check.sh deadcode ;;
  backend) sh scripts/run-backend.sh ;;
  frontend) sh scripts/run-frontend.sh ;;
  build) sh scripts/run-build.sh ;;
  security) sh scripts/run-security.sh ;;
  security-pip) sh scripts/run-security-pip.sh ;;
  security-node) sh scripts/run-security-node.sh ;;
  ci)
    sh scripts/check.sh lint
    sh scripts/check.sh comments
    sh scripts/check.sh deadcode
    sh scripts/run-backend.sh
    sh scripts/run-frontend.sh
    ;;
  *) echo "usage: $0 [ci|quality|backend|frontend|build|security]" >&2; exit 2 ;;
esac
