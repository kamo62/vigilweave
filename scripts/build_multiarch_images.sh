#!/usr/bin/env bash
set -euo pipefail

target_group="${1:-default}"

docker buildx bake --file docker-bake.hcl "${target_group}"
