# Agent overlay

Take the user INTERNAL build as the product core. Layer this repository overlay on top of it to produce a production app. Do not replace the internal core with a greenfield rewrite.

## Overlay to apply

- F/A-18 program access portal (Flask + React/Vite, mock Okta)
- Auth-gated Doxygen docs reader at `/docs` via `/api/docs/*`
- Section 508 / focus: move focus to `main` after route change; no boxed h1 chrome
- Five-part comments (WHAT / WHY / WHO / WHERE / HOW) on every new function
- Portable quality contract: `make ci` / `scripts/pipeline.sh`
- Hosted pipelines: GitHub Actions (`.github/workflows/ci.yml` + `security.yml`) and GitLab CI (`.gitlab-ci.yml`). Both call the same `make ci` contract. Do not invent a GitLab remote or register a runner.

## Product locks (do not regress)

- No flying Hornet animation
- No flyouts (`data-flyout`, `flyout.css`, `annotateProseLinks`, `title=` tooltips)
- No DocsHero / photo band on `/docs`
- No boxed h1 focus chrome; focus goes to `main`
- Header: mark + program name only
- Footer: mark, demo line, copyright only

## DO NOT

- Do NOT message the user
- Do NOT print tokens or secrets
- Do NOT run `git config`
- Do NOT force-push
- Do NOT clone a repo
- Do NOT push `.env`, `.venv`, `node_modules`, `__pycache__`, or mailbox dumps
