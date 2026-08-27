#!/bin/sh
# WHAT: Portable product contract for GitHub, GitLab, and a laptop.
# WHY: Hosted YAML must not invent a different set of gates than make ci.
# WHO: make ci, GitHub Actions, GitLab CI, and the agents overlay.
# WHERE: Repo root. First argument is the slice name (default ci).
# HOW: Each slice calls the same script the matching make target calls.
#      ci is quality plus backend plus frontend plus build. No empty waiter.

set -e
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
slice=${1:-ci}
if [ "$slice" = all ]; then slice=ci; fi
case "$slice" in
  lint) sh scripts/check.sh lint ;;
  comments) sh scripts/check.sh comments ;;
  deadcode) sh scripts/check.sh deadcode ;;
  quality) sh scripts/check.sh comments; sh scripts/check.sh deadcode ;;
  backend) sh scripts/run-backend.sh ;;
  frontend) sh scripts/run-frontend.sh ;;
  build) sh scripts/run-build.sh ;;
  security) sh scripts/run-security.sh ;;
  security-pip) sh scripts/run-security-pip.sh ;;
  security-node) sh scripts/run-security-node.sh ;;
  ci)
    sh scripts/check.sh comments
    sh scripts/check.sh deadcode
    sh scripts/run-backend.sh
    sh scripts/run-frontend.sh
    sh scripts/run-build.sh
    ;;
  *) echo "usage: $0 [ci|quality|backend|frontend|build|security]" >&2; exit 2 ;;
esac
