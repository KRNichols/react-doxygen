# WHAT: Local names for every pipeline slice.
# WHY: Humans and hosted CI must type the same words or the gates drift.
# WHO: Developers, GitHub Actions, and GitLab CI.
# WHERE: Repo root. Each target calls one script.
# HOW: ci is quality plus backend plus frontend plus build. There is no empty ci target.

.PHONY: --all check lint comments deadcode test ci security security-pip security-node backend frontend build quality agents

check:
	sh scripts/check.sh check

lint:
	sh scripts/check.sh lint

comments:
	sh scripts/check.sh comments

deadcode:
	sh scripts/check.sh deadcode

quality:
	sh scripts/check.sh comments
	sh scripts/check.sh deadcode

backend:
	sh scripts/run-backend.sh

frontend:
	sh scripts/run-frontend.sh

build:
	sh scripts/run-build.sh

test: backend frontend

ci: quality backend frontend build

security:
	sh scripts/run-security.sh

security-pip:
	sh scripts/run-security-pip.sh

security-node:
	sh scripts/run-security-node.sh

agents:
	python3 scripts/check-agents.py

--all:
	@true
