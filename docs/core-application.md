# VigilWeave core application

Source-only application: Python backend, React frontend, database migrations and
build configuration. Released under the MIT licence in `LICENSE`.

No third-party packages, Python runtimes, scanner binaries, compiled assets, tests,
Docker files, CI/IDE extensions or separate services are bundled. Dependencies must
be installed separately. This is not an offline installation package.

## Backend

Requires Python 3.14+ and Git for repository scans. From the extracted directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export VIGILWEAVE_WEB_BASE_URL=http://127.0.0.1:5173
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

SQLite, local login and synchronous scans are the defaults. For repeated starts,
keep your generated session secret in the local ignored `.env` file; changing it
invalidates existing sessions. Never publish that file or the database.

## Frontend

Requires Node.js 20.19+ (or 22.12+) and Bun. In another terminal:

```sh
cd frontend
bun install --frozen-lockfile
bun run dev --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/setup` to create your administrator account.
`bun run build` creates the production frontend and generates API types from the
included `docs/openapi.json` contract. Scanner tools, rules and vulnerability
databases must be supplied separately where required.

This is an educational development application, not a verified production or
sandboxed scanning deployment. Use synthetic data and trusted test repositories.
