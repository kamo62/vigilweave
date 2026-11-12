#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
python -m pytest -m e2e
