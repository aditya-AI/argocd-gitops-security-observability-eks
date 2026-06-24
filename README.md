# Argo CD GitOps, Security, and Observability on EKS

This repo reuses a familiar multiservice Kubernetes application and focuses on a different question: how do we operate that workload more cleanly on Amazon EKS once the first deployment already works?

The application shape stays intentionally simple:

- `api`: FastAPI service
- `worker`: background processor
- `migrator`: one-shot schema job
- `postgres`: stateful database

What changes in this repo is the operating layer around that app:

- Argo CD becomes the deployment control plane
- Kustomize drives workload customization
- Helm, through Argo CD, installs shared platform components
- RBAC and `NetworkPolicy` tighten the workload namespace
- Prometheus and OpenTelemetry add metrics and traces

## Repo layout

```text
apps/
  api/
  worker/
  migrator/
argocd/
  bootstrap/
  root/
k8s/
  app/
    base/
    overlays/
      gitops/
examples/
scripts/
```

## Lesson files

The lesson material is split into two connected lessons in the same module:

- `ARGOCD_GITOPS_ON_EKS_ARTICLE.md`
- `SECURITY_OBSERVABILITY_ON_EKS_ARTICLE.md`

The intended reading order is:

1. `ARGOCD_GITOPS_ON_EKS_ARTICLE.md`
2. `SECURITY_OBSERVABILITY_ON_EKS_ARTICLE.md`

The first lesson establishes the GitOps foundation on EKS. The second lesson builds directly on that same repo, namespace, and Argo CD workflow to explain security and observability.

Supporting examples for the security and observability lesson live here:

- `examples/external-secret.yaml`
- `examples/promql-queries.md`

## Important paths

### Argo CD bootstrap and root layer

- `argocd/bootstrap/root-application.yaml`
- `argocd/root/bootstrap-settings-configmap.yaml`
- `argocd/root/platform-project.yaml`
- `argocd/root/workloads-project.yaml`
- `argocd/root/workload-app.yaml`
- `argocd/root/kube-prometheus-stack-app.yaml`
- `argocd/root/opentelemetry-collector-app.yaml`

### Workload overlay

- `k8s/app/overlays/gitops/kustomization.yaml`
- `k8s/app/overlays/gitops/gitops-settings-configmap.yaml`
- `k8s/app/overlays/gitops/patch-sync-waves.yaml`
- `k8s/app/overlays/gitops/serviceaccounts.yaml`
- `k8s/app/overlays/gitops/rbac.yaml`
- `k8s/app/overlays/gitops/networkpolicies.yaml`
- `k8s/app/overlays/gitops/service-monitor.yaml`
- `k8s/app/overlays/gitops/patch-api-observability.yaml`
- `k8s/app/overlays/gitops/patch-worker-observability.yaml`

### Verification helpers

- `scripts/verify-argocd-apps.sh`
- `scripts/verify-security-observability.sh`

## Common workflow

### Build local images

```bash
./scripts/build-images.sh
```

### Push images to Amazon ECR

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=123456789012
./scripts/push-ecr.sh
```

### Update repo-specific settings

Edit these files before syncing:

- `k8s/app/overlays/gitops/gitops-settings-configmap.yaml`
- `argocd/root/bootstrap-settings-configmap.yaml`

Replace the placeholder values for:

- ECR image names
- IRSA role ARNs
- ingress host
- Git repository URL

### Render the workload manifests before sync

```bash
./scripts/render-workload.sh
```

### Install Argo CD and bootstrap the root app

```bash
./scripts/install-argocd.sh

export GITOPS_REPO_URL=https://github.com/your-org/argocd-gitops-security-observability-eks.git
export GITOPS_REVISION=main
./scripts/bootstrap-root-app.sh
```

The install script uses server-side apply on the upstream Argo CD manifest so large CRDs such as `applicationsets.argoproj.io` do not fail with Kubernetes annotation-size limits.

## What this repo is designed to teach

This repo is intentionally opinionated. It is meant to show:

- why GitOps on EKS is more repeatable than hand-running `kubectl apply`
- how Argo CD can manage both workload manifests and shared platform components
- how namespace security belongs in the same repository conversation as delivery
- how metrics and traces become easier to operate when they are wired in from the start
