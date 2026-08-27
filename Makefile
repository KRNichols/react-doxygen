.PHONY: check lint comments deadcode test ci security security-pip security-node backend frontend build quality

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
