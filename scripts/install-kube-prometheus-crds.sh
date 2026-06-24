#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_VERSION="$(awk -F'"' '/kubePrometheusChartVersion:/ {print $2}' "$ROOT_DIR/argocd/root/bootstrap-settings-configmap.yaml")"
CHART_VERSION="${KUBE_PROMETHEUS_STACK_VERSION:-$DEFAULT_VERSION}"
TMP_FILE="$(mktemp /tmp/kube-prometheus-stack-crds.XXXXXX.yaml)"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community >/dev/null
helm show crds prometheus-community/kube-prometheus-stack --version "$CHART_VERSION" > "$TMP_FILE"

if [[ ! -s "$TMP_FILE" ]]; then
  echo "No CRDs were returned for kube-prometheus-stack version $CHART_VERSION" >&2
  exit 1
fi

kubectl apply --server-side -f "$TMP_FILE"
echo "Installed kube-prometheus-stack CRDs for chart version $CHART_VERSION"
