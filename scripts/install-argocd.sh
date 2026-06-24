#!/usr/bin/env bash
set -euo pipefail

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
# Use server-side apply so large CRDs such as ApplicationSet do not hit the
# client-side last-applied annotation size limit.
kubectl apply --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
