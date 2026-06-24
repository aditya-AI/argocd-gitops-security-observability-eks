#!/usr/bin/env bash
set -euo pipefail

WORKLOAD_NAMESPACE="${WORKLOAD_NAMESPACE:-gitops-demo}"
OBS_NAMESPACE="${OBS_NAMESPACE:-observability}"

printf 'Security resources in namespace %s\n' "$WORKLOAD_NAMESPACE"
kubectl get sa,role,rolebinding,networkpolicy,servicemonitor -n "$WORKLOAD_NAMESPACE"

printf '\nWorkload resources in namespace %s\n' "$WORKLOAD_NAMESPACE"
kubectl get pods,svc,ingress,job -n "$WORKLOAD_NAMESPACE"

printf '\nObservability namespace pods in %s\n' "$OBS_NAMESPACE"
kubectl get pods -n "$OBS_NAMESPACE"
