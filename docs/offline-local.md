# Offline local-run bundle

This ZIP runs VigilWeave locally without Docker, Bun, Node, a Redis server or an
internet connection. It contains source, a prebuilt frontend, Python 3.14.10 Linux
distributions, exact-version Python wheels, and Gitleaks 8.30.0. Bandit 1.9.4 and
Ruff 0.15.6 use the versions installed on the preparation machine.

## Linux requirements

- x86-64 or ARM64 (aarch64), with glibc 2.34 or newer, such as Ubuntu 22.04+ or Debian 12+.
- Git, tar, `sha256sum`, `getconf`, a shell and an unzip utility already installed.
- A browser and sufficient writable disk space for the ZIP, extracted assets and scans.
- A normal user account. Do not run the application as root.

Alpine/musl, older glibc, Windows and macOS are not installer targets. The Linux
assets were prepared on macOS. Cross-platform wheel resolution and archive checks
are not evidence that installation or scanning has run on Linux. See `BUNDLE.json`
for provenance and the exact targets. The Mac virtual environment is not included.

## Install and start without internet

Transfer the ZIP and its `.sha256` file to Linux. In their containing directory:

```sh
sha256sum --check vigilweave-offline-linux.zip.sha256
unzip vigilweave-offline-linux.zip
cd vigilweave-offline
sh scripts/offline/setup.sh
sh scripts/offline/start.sh --repos /absolute/path/to/repositories
```

If the ZIP has a different name, use its matching checksum filename. Setup checks
all bundle hashes, extracts the matching portable Python distribution locally and
installs wheels with `--no-index --require-hashes`. It does not use apt, pip indexes
or downloads, and does not change system Python. Re-running setup reuses the local
environment. Do not move the extracted folder after setup; virtual environments
contain absolute paths. Instead, extract a fresh copy at the final location.

Open `http://127.0.0.1:8000/setup` and create your local administrator. Use
`127.0.0.1` consistently, rather than switching between that name and `localhost`.
The frontend and API share that origin, including browser-route refreshes.
External font links are removed from this build; existing system-font fallbacks apply.
Stop with Ctrl+C. Use `--port 8001` if port 8000 is occupied.

The launcher binds only to loopback, uses SQLite and synchronous scanning, and
ignores application settings and credentials inherited from the shell. Persistent
state is kept in `.offline-state/`, including a newly generated session secret,
database and editable scanner configuration. Keep this directory private; never
include it in another submission ZIP. An existing `.env` there is rejected.
`--state /absolute/path/to/private-state` selects another private state directory.

Community feature limits remain the default. For disposable local development,
`--all-features` explicitly enables the existing development-only licence bypass:

```sh
sh scripts/offline/start.sh --repos /absolute/path/to/repositories --all-features
```

This is not a production deployment or a scanner sandbox. Use synthetic data,
disposable credentials and trusted test repositories. Disabled repository-build
adapters reduce risk, but do not isolate scanner processes from your account.

## Local scans

Put real Git repositories under the directory passed to `--repos`. A source ZIP
without a Git repository is not a scan target until you initialise and commit it:

```sh
git -C /absolute/path/to/repositories/example init
git -C /absolute/path/to/repositories/example add .
git -C /absolute/path/to/repositories/example \
  -c user.name='Offline Example' -c user.email='offline@example.com' \
  commit -m 'Synthetic offline scan input'
```

Do not initialise or commit private source unintentionally. Local clones analyse
committed files, not uncommitted working-tree edits.

Submit `file:///absolute/path/to/repositories/example` as the repository URL in
the scan form. The path must remain inside the allowed repository root. If no
branch is required, leave it blank. Alternatively, create an API key under
Settings > API Keys and submit this JSON to `POST /api/v1/scans/` using
`X-API-Key: YOUR_LOCAL_API_KEY_HERE`:

```json
{"repo":"file:///absolute/path/to/repositories/example","scan_type":"comprehensive"}
```

The offline profile uses:

| Scanner | Available coverage |
| --- | --- |
| Gitleaks | Secret patterns in committed Git history, using its built-in rules |
| Bandit | Python security checks |
| Ruff | Python quality checks |
| Built-in analysis | File/language metrics and existing quality heuristics |

`fast` and `comprehensive` both run the bundled tools; `security-only` omits Ruff.
Non-Python repositories do not receive Bandit/Ruff coverage. Inspect each scan's
tool executions, not only its gate: a passing gate is not complete security coverage.
This package does not change the application's existing skipped-tool semantics.

Semgrep registry rules, dependency/container vulnerability databases, IaC scanners,
ESLint, Java, .NET and Android tooling are not included or enabled. Remote SCM,
SSO and billing require their external services. PDF generation is not included
because Playwright/Chromium and their system dependencies are omitted. Existing
JSON, CSV and SARIF endpoints do not need a browser engine.

For a disposable end-to-end check, including local admin setup and real scanner
execution against vulnerable and clean synthetic Git repositories:

```sh
.venv-offline/bin/python scripts/offline/smoke_scan.py
```

This uses a temporary database and test accounts, not your persistent instance.
It requires all three scanner binaries and fails if a tool is skipped or fails.
Normal backend pytest fixtures stub native scanners and do not prove real scanning.

## Source and rebuilding

Python application edits run directly from source. Restart the launcher after edits.
The ZIP includes the frontend source and build configuration, but not Linux
`node_modules` or the Node/Bun build toolchain. Rebuilding the frontend requires a
separately prepared development environment; it is not part of this local-run ZIP.
Do not use root `requirements.txt` to install offline: it includes omitted optional
tools. The authoritative bundle locks are `vendor/requirements-<arch>.txt`.

To prepare a new ZIP on the connected machine using the existing dependencies:

```sh
python3 scripts/offline/build_bundle.py
```

The preparation Python must have pip, with `uv`, Bun, `.venv` and
`frontend/node_modules` already available. Preparation downloads Linux distributions,
wheels and scanner releases and verifies upstream Python/Gitleaks checksums. It
never copies a Mac virtual environment or Mac-native Node modules. Only setup and
runtime, not bundle preparation, are offline.

`LICENSE`, wheel-embedded licences, portable-Python licence material and frontend
third-party notices are retained. Git history, credentials, private runtime data,
Docker assets, task/agent/handoff/PRD files and design mockups are excluded. Generated
dependency archives remain outside Git.
