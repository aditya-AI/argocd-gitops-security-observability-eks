#!/usr/bin/env bash
set -euo pipefail

GITOPS_REPO_URL="${GITOPS_REPO_URL:?set GITOPS_REPO_URL, e.g. https://github.com/your-org/argocd-gitops-security-observability-eks.git}"
GITOPS_REVISION="${GITOPS_REVISION:-main}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

sed \
  -e "s|__GITOPS_REPO_URL__|$GITOPS_REPO_URL|g" \
  -e "s|__GITOPS_REVISION__|$GITOPS_REVISION|g" \
  "$ROOT_DIR/argocd/bootstrap/root-application.yaml"
