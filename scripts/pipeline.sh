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
  # WHAT: Language lint only.
  # WHY: Style errors should fail before tests run.
  # WHO: make lint and anyone who calls this script with lint.
  # WHERE: backend Python and frontend JS through check.sh.
  # HOW: Shell out to scripts/check.sh lint.
  lint) sh scripts/check.sh lint ;;
  # WHAT: Five-part comment inventory on the whole first-party tree.
  # WHY: A docs-only change is not a comment upgrade; --all must still be green.
  # WHO: make comments, make quality, and the hosted quality job.
  # WHERE: backend/scripts/check_comments.py through check.sh.
  # HOW: Always pass --all so the gate does not shrink to a delta.
  comments) sh scripts/check.sh comments ;;
  # WHAT: Unused import and unused variable scan.
  # WHY: Dead names should not land just because tests still pass.
  # WHO: make deadcode, make quality, and the hosted quality job.
  # WHERE: backend Python through check.sh.
  # HOW: ruff rules F401 and F841 only.
  deadcode) sh scripts/check.sh deadcode ;;
  # WHAT: Declared-package allowlist gate.
  # WHY: A new first-party dependency must fail CI until it is on the list.
  # WHO: make packages, make quality, make ci.
  # WHERE: approved-packages.json vs the requirement and package.json manifests.
  # HOW: Shell out to scripts/check.sh packages.
  packages) sh scripts/check.sh packages ;;
  # WHAT: Comments, unused-code, and the approved-package allowlist.
  # WHY: The hosted quality job is this trio, not lint plus tests.
  # WHO: make quality and GitHub/GitLab quality jobs.
  # WHERE: Same scripts as the comments, deadcode, and packages arms.
  # HOW: Run comments, deadcode, then packages, in that order.
  quality) sh scripts/check.sh comments; sh scripts/check.sh deadcode; sh scripts/check.sh packages ;;
  # WHAT: Python lint and tests with a coverage floor.
  # WHY: Auth, copy, signup, and docs handlers must stay green.
  # WHO: make backend, make test, make ci, hosted backend job.
  # WHERE: backend Python and backend/tests.
  # HOW: Shell out to scripts/run-backend.sh.
  backend) sh scripts/run-backend.sh ;;
  # WHAT: JavaScript lint and unit tests. Not the production bundle.
  # WHY: Keep a test fail distinct from a broken production bundle.
  # WHO: make frontend, make test, make ci, hosted frontend job.
  # WHERE: frontend lint and unit tests.
  # HOW: Shell out to scripts/run-frontend.sh.
  frontend) sh scripts/run-frontend.sh ;;
  # WHAT: Production frontend bundle only.
  # WHY: Flask serves the built files. This is not a second frontend job.
  # WHO: make build, make ci, hosted build job.
  # WHERE: frontend production bundler.
  # HOW: Shell out to scripts/run-build.sh.
  build) sh scripts/run-build.sh ;;
  # WHAT: Python and Node advisory scans together.
  # WHY: Local twin of the hosted security workflow.
  # WHO: make security and anyone who calls this script with security.
  # WHERE: The two security runner scripts.
  # HOW: Shell out to scripts/run-security.sh.
  security) sh scripts/run-security.sh ;;
  # WHAT: Python package advisory scan.
  # WHY: The API stack must not ship a known-bad wheel.
  # WHO: make security-pip and the hosted pip-audit job.
  # WHERE: backend/requirements.txt.
  # HOW: Shell out to scripts/run-security-pip.sh.
  security-pip) sh scripts/run-security-pip.sh ;;
  # WHAT: Production Node advisory scan.
  # WHY: The shipped UI must not depend on a high-severity package.
  # WHO: make security-node and the hosted node-audit job.
  # WHERE: frontend production tree.
  # HOW: Shell out to scripts/run-security-node.sh.
  security-node) sh scripts/run-security-node.sh ;;
  # WHAT: Full product contract. Same order as Makefile ci.
  # WHY: GitHub, GitLab, and a laptop must run the same four slices.
  # WHO: make ci, this script with no args, and the agents overlay.
  # WHERE: quality, backend, frontend, then build. No dummy waiter.
  # HOW: comments, deadcode, packages, backend, frontend, then build, each via its script.
  ci)
    sh scripts/check.sh comments
    sh scripts/check.sh deadcode
    sh scripts/check.sh packages
    sh scripts/run-backend.sh
    sh scripts/run-frontend.sh
    sh scripts/run-build.sh
    ;;
  # WHAT: Unknown slice name.
  # WHY: A typo should fail closed with a usage line, not run ci by accident.
  # WHO: Anyone who calls this script with a name that is not a slice.
  # WHERE: stderr, then exit 2.
  # HOW: Print the accepted slice names and stop.
  *) echo "usage: $0 [ci|quality|backend|frontend|build|security]" >&2; exit 2 ;;
esac
