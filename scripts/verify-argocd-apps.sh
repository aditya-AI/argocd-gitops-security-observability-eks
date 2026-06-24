#!/usr/bin/env bash
set -euo pipefail

ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"

printf 'Argo CD applications in namespace %s\n' "$ARGOCD_NAMESPACE"
kubectl get applications -n "$ARGOCD_NAMESPACE"

printf '\nArgo CD projects in namespace %s\n' "$ARGOCD_NAMESPACE"
kubectl get appprojects -n "$ARGOCD_NAMESPACE"

printf '\nArgo CD control plane pods in namespace %s\n' "$ARGOCD_NAMESPACE"
kubectl get pods -n "$ARGOCD_NAMESPACE"
