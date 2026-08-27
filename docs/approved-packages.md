# Approved packages

Declared first-party packages for this repo. The pipeline fails if `backend/requirements.txt`, `backend/requirements-dev.txt`, or `frontend/package.json` names anything else.

This is a label on the current tree. It is not an ATO, not FedRAMP, and not scanner-proof. Transitive wheels and `node_modules` children are not on this list.

Machine copy: [`approved-packages.json`](../approved-packages.json). Gate: `make packages` (also `make check` and `make ci`).

## Backend

Product:

- Flask `>=3.0.0`
- flask-cors `>=4.0.0`
- python-dotenv `>=1.0.0`
- itsdangerous `>=2.1.0`
- boto3 `>=1.34.0`
- ruff `>=0.6.0`

Already in the tree (tests and advisory scan):

- pytest `>=8.0.0`
- pytest-cov `>=5.0.0`
- pip-audit `>=2.7.0`

## Frontend

Product:

- react `^18.3.1`
- react-dom `^18.3.1`
- react-router-dom `^6.26.2`

Existing vite / vitest / eslint / testing-library set:

- @vitejs/plugin-react `^4.3.1`
- vite `^5.4.8`
- vitest `^2.1.0`
- jsdom `^25.0.0`
- @testing-library/react `^16.0.1`
- @testing-library/jest-dom `^6.5.0`
- eslint `^9.10.0`
- globals `^15.9.0`
