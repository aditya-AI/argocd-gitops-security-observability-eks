#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

build() {
  local name="$1"
  local dir="$2"
  echo "Building $name ..."
  docker build -t "$name" \
    --build-arg HTTP_PROXY="${HTTP_PROXY:-}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY:-}" \
    --build-arg NO_PROXY="${NO_PROXY:-}" \
    "$ROOT_DIR/$dir"
}

build "gitops-demo-api:local" "apps/api"
build "gitops-demo-worker:local" "apps/worker"
build "gitops-demo-migrator:local" "apps/migrator"

echo "Done."
