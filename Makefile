# WHAT: Local names for every pipeline slice.
# WHY: Humans and hosted CI must type the same words or the gates drift.
# WHO: Developers, GitHub Actions, and GitLab CI.
# WHERE: Repo root. Each target calls one script.
# HOW: ci is quality plus backend plus frontend plus build. There is no empty ci target.

.PHONY: --all check lint comments deadcode packages test ci security security-pip security-node backend frontend build quality agents

# WHAT: Fast lint plus the five-part comment gate.
# WHY: Catch style and missing comments without running the full test suite.
# WHO: A developer on a laptop, or make check --all.
# WHERE: scripts/check.sh check.
# HOW: Shell out to check.sh (lint, comments, packages). The --all phony exists so GNU make accepts the flag.
check:
	sh scripts/check.sh check

# WHAT: Language lint only.
# WHY: Split out of check so CI can name the slice.
# WHO: make lint and scripts/pipeline.sh lint.
# WHERE: backend Python via ruff; frontend JS via eslint when installed.
# HOW: scripts/check.sh lint.
lint:
	sh scripts/check.sh lint

# WHAT: Five-part comment inventory on the whole first-party tree.
# WHY: A docs-only change is not a comment upgrade; --all must still be green.
# WHO: make comments, make quality, and the hosted quality job.
# WHERE: backend/scripts/check_comments.py --all.
# HOW: scripts/check.sh comments.
comments:
	sh scripts/check.sh comments

# WHAT: Unused import and unused variable scan.
# WHY: Dead names should not land just because tests still pass.
# WHO: make deadcode, make quality, and the hosted quality job.
# WHERE: backend Python via unused-import and unused-variable rules.
# HOW: scripts/check.sh deadcode.
deadcode:
	sh scripts/check.sh deadcode

# WHAT: Declared-package allowlist gate.
# WHY: A new first-party dependency must fail CI until it is on the list.
# WHO: make packages, make check, make quality, make ci.
# WHERE: approved-packages.json vs requirements files and frontend/package.json.
# HOW: scripts/check.sh packages.
packages:
	sh scripts/check.sh packages

# WHAT: Comments, unused-code, and the approved-package allowlist.
# WHY: The hosted quality job is this trio, not lint plus tests.
# WHO: make quality and GitHub/GitLab quality jobs.
# WHERE: Same scripts as comments, deadcode, and packages.
# HOW: Run the three slices in that order.
quality:
	sh scripts/check.sh comments
	sh scripts/check.sh deadcode
	sh scripts/check.sh packages

# WHAT: Python lint and tests with a coverage floor.
# WHY: Auth, copy, signup, and docs handlers must stay green.
# WHO: make backend, make test, make ci, hosted backend job.
# WHERE: backend Python and backend/tests.
# HOW: scripts/run-backend.sh.
backend:
	sh scripts/run-backend.sh

# WHAT: JavaScript lint and unit tests. Not the production bundle.
# WHY: Keep a test fail distinct from a broken production bundle.
# WHO: make frontend, make test, make ci, hosted frontend job.
# WHERE: frontend lint and unit tests.
# HOW: scripts/run-frontend.sh.
frontend:
	sh scripts/run-frontend.sh

# WHAT: Production frontend bundle only.
# WHY: Flask serves the built files. This is not a second frontend job.
# WHO: make build, make ci, hosted build job.
# WHERE: frontend production bundler.
# HOW: scripts/run-build.sh. Fresh install when CI is set or packages are missing.
build:
	sh scripts/run-build.sh

# WHAT: Backend tests plus frontend tests.
# WHY: A short name for both language suites without quality or build.
# WHO: Developers who want tests only.
# WHERE: The backend and frontend targets above.
# HOW: Make prerequisite expansion.
test: backend frontend

# WHAT: Portable product contract.
# WHY: GitHub, GitLab, and a laptop must run the same four slices.
# WHO: make ci, scripts/pipeline.sh ci, the agents overlay.
# WHERE: quality (comments, deadcode, packages), backend, frontend, then build. No dummy waiter.
# HOW: Prerequisite list. Matches pipeline.sh ci.
ci: quality backend frontend build

# WHAT: Python and Node advisory scans together.
# WHY: Local twin of the hosted security workflow.
# WHO: make security.
# WHERE: scripts/run-security.sh, which calls the two slices below.
# HOW: Python requirements scan, then production Node high-severity scan.
security:
	sh scripts/run-security.sh

# WHAT: Python package advisory scan.
# WHY: The API stack must not ship a known-bad wheel.
# WHO: make security-pip and the hosted pip-audit job.
# WHERE: backend/requirements.txt.
# HOW: scripts/run-security-pip.sh.
security-pip:
	sh scripts/run-security-pip.sh

# WHAT: Production Node advisory scan.
# WHY: The shipped UI must not depend on a high-severity package.
# WHO: make security-node and the hosted node-audit job.
# WHERE: frontend production tree.
# HOW: scripts/run-security-node.sh.
security-node:
	sh scripts/run-security-node.sh

# WHAT: Docs-writer loop chrome gates.
# WHY: Overlay locks stay in-repo: no Hornet, no flyouts, no DocsHero, focus to main.
# WHO: make agents and the hosted Agents overlay.
# WHERE: scripts/check-agents.py.
# HOW: Fail if a forbidden file or chrome marker returns.
agents:
	python3 scripts/check-agents.py

# WHAT: Accept make check --all on GNU make.
# WHY: The comment checker already uses --all; make should not treat it as unknown.
# WHO: Local make check --all.
# WHERE: This phony target.
# HOW: Do nothing. check.sh comments already passes --all.
--all:
	@true
