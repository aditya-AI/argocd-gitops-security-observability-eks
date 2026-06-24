#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:?set AWS_REGION, e.g. us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?set AWS_ACCOUNT_ID}"
ECR_PREFIX="${ECR_PREFIX:-gitops-demo}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

ensure_repo() {
  local repo="$1"
  if ! aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$repo" >/dev/null 2>&1; then
    aws ecr create-repository --region "$AWS_REGION" --repository-name "$repo" >/dev/null
  fi
}

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

for service in api worker migrator; do
  repo="${ECR_PREFIX}-${service}"
  ensure_repo "$repo"

  local_tag="gitops-demo-${service}:local"
  remote_tag="${ECR_REGISTRY}/${repo}:latest"

  echo "Pushing ${local_tag} -> ${remote_tag}"
  docker tag "$local_tag" "$remote_tag"
  docker push "$remote_tag"
done

cat <<EOF
Images pushed successfully.
Update:
  k8s/app/overlays/gitops/gitops-settings-configmap.yaml
Then commit the repo and bootstrap Argo CD.
EOF
