# Managing Kubernetes Applications on Amazon EKS with Argo CD and GitOps

If you have already deployed a Kubernetes application to Amazon EKS once, you have crossed an important milestone. You proved that your containers build, your manifests work, your AWS networking path is valid, and your application can survive outside a local cluster.

That is the beginning of the cloud story, not the end of it.

The harder question comes next:

How do you keep that cluster honest after the first deployment?

This lesson is the first half of a two-lesson module. In this lesson, we take a familiar multiservice application and change the operating model around it. The application itself stays intentionally simple:

- an `api` service
- a `worker` service
- a one-shot `migrator` Job
- a `postgres` database

We keep that shape on purpose. If we changed the application and the operating model at the same time, readers would have to untangle two different lessons at once. By keeping the workload familiar, we can focus on the real goal:

- why GitOps matters on EKS
- what Argo CD actually does
- how to bootstrap Argo CD into a cluster
- how the app-of-apps pattern works
- how Git becomes the source of truth for day-2 changes

By the end of this lesson, readers should understand:

- why manual `kubectl apply` workflows become fragile over time
- how Argo CD continuously compares Git against the live cluster
- how this repo is structured around bootstrap, root applications, and a workload overlay
- how key YAML files such as `root-application.yaml`, `kustomization.yaml`, `workload-app.yaml`, and `gitops-settings-configmap.yaml` fit together
- how image updates and rollbacks should flow through Git instead of ad hoc cluster edits

This lesson stays focused on delivery and reconciliation. In the next lesson, we will take this exact GitOps-managed workload and harden it with security controls, metrics, and traces.

**Figure 1. High-level GitOps workflow for the EKS workload.**

Nano Banana prompt: Create a polished engineering-blog architecture diagram on a white background. Show a developer committing Kubernetes changes to Git on the left. Show Git as the source of truth. Show Argo CD inside an Amazon EKS cluster continuously syncing from Git into the cluster. Add a small crossed-out `manual kubectl edits` callout to show that manual cluster drift is discouraged. Inside the cluster, show four workload components labeled `api`, `worker`, `migrator`, and `postgres`. Show an AWS Application Load Balancer routing traffic to the API. Use AWS-inspired blue-gray colors, crisp labels, subtle shadows, and a clean lesson style.

## Why Deploying to EKS Once Is Not the Same as Operating on EKS

The first big idea in this lesson is simple:

Getting an application onto EKS does not automatically give you a clean operating model.

You can have a working cluster and still have a workflow that becomes painful a week later.

### Manual cluster edits feel fine right up until they do not

Manual cluster management always feels reasonable at the beginning.

You run a few commands. You apply a few manifests. You patch a Deployment. You rerun a Job. You fix something small from the terminal. The system comes up, and it is tempting to call that success.

The trouble appears later:

- the live cluster drifts away from what the repo says
- teammates cannot review infrastructure changes with the same discipline as code changes
- recreating the environment becomes harder than it should be
- rollbacks turn into memory exercises instead of a repeatable workflow

That is the moment when GitOps stops sounding theoretical and starts sounding practical.

### GitOps in plain English

GitOps can sound bigger than it really is. In plain English, it means:

1. Store the desired cluster state in Git.
2. Run a controller that watches Git.
3. Let that controller reconcile the live cluster until it matches the desired state.

In this repo, Argo CD is that controller.

So the cluster is no longer defined by "whatever someone last did in a terminal." The cluster becomes the running copy of what the repository says should exist.

### What Argo CD actually does

Argo CD is a GitOps controller that runs inside Kubernetes. Its job is to:

- watch a Git repository, Helm chart, or another declared source
- compare the desired state against live cluster state
- show when something is out of sync
- reconcile the cluster back to the declared state

The beginner-friendly mental model is this:

Argo CD sits between Git and your cluster and keeps asking one question:

"Does the live cluster still match what Git says it should be?"

If the answer is no, Argo CD can show the drift and, if configured to do so, correct it.

### A few Argo CD terms are worth learning early

Before readers open the UI, it helps to define a few words they will see repeatedly:

- `Synced`: the live cluster matches Git
- `OutOfSync`: the live cluster no longer matches Git
- `drift`: any difference between desired state and live state
- `prune`: delete resources that were removed from the desired state
- `self-heal`: automatically correct changes that happened outside Git

These terms are not difficult, but they matter because they turn the Argo CD UI from a wall of status badges into something readers can actually interpret.

**Figure 2. Manual EKS management versus a GitOps workflow with Argo CD.**

Nano Banana prompt: Create a side-by-side comparison infographic for a technical lesson. On the left, show a `Manual EKS Management` workflow with a user running kubectl commands, direct cluster edits, drift, and uncertainty. On the right, show a `GitOps with Argo CD` workflow where Git is the source of truth and Argo CD reconciles the cluster automatically. Use a clean white background, modern flat vector style, engineering-friendly typography, and simple arrows that make the difference obvious.

## Why Argo CD Fits This Repo Better Than Flux

Flux is a valid GitOps tool, so this choice deserves a straight answer.

We are not using Argo CD because Flux is wrong. We are using Argo CD because, for this particular teaching repo, it explains the operating model more clearly.

### Argo CD gives beginners a more visible control plane

Argo CD is a strong fit here because:

- its application model is easy to explain
- the app-of-apps pattern maps cleanly to how this repo is organized
- the UI makes sync, health, and drift easy to show in screenshots
- one root application can clearly fan out into platform apps and workload apps

### Flux is still a good option, just a different teaching surface

Flux tends to feel more controller-centric and more Kubernetes-native in presentation. Many teams like that. It is absolutely a production-grade choice.

For a course repo, though, Argo CD gives us a clearer beginner path:

- one visible `Application` object per managed concern
- one clear drift story
- one UI that shows what is healthy, what is broken, and what is waiting to sync

That makes Argo CD the better teaching choice here, even though the underlying GitOps principles would still apply with Flux.

## What Stays the Same, and What Actually Changes

The application shape is the same as before:

- `api`: FastAPI service
- `worker`: background processor
- `migrator`: schema Job
- `postgres`: stateful database

What changes in this lesson is the control plane around that application.

By the end, readers will understand a repo model where:

- Argo CD becomes the deployment control plane
- Kustomize still shapes the Kubernetes manifests
- a tiny bootstrap step points Argo CD at the repo
- a root application creates child applications for both platform and workload concerns
- normal day-2 changes flow through Git instead of live patching

That is a meaningful shift. It turns Kubernetes from "something we can deploy" into "something we can keep aligned over time."

## How the Repository Is Organized

The easiest way to understand this repo is to separate application code from operating-model code.

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
scripts/
```

### `apps/` still holds the application code

The application code remains in:

```text
apps/
  api/
  worker/
  migrator/
```

That continuity matters. Readers are not being asked to learn a new business domain just to understand GitOps.

### `argocd/bootstrap/` solves the first-application problem

GitOps introduces a very practical question:

If Argo CD is supposed to manage the cluster from Git, how do we get Argo CD itself into the cluster in the first place?

That is what the bootstrap layer solves.

### `argocd/root/` defines the control plane Argo CD should manage

Once Argo CD is running, it needs a directory that tells it what else belongs under management.

That is the job of `argocd/root/`. This layer defines:

- shared bootstrap settings
- `AppProject` boundaries
- child applications for platform components
- the child application that points at the workload overlay

### `k8s/app/overlays/gitops/` is the real workload target

The root application does not embed every Deployment, Job, Service, and Ingress directly. Instead, it points a child application at:

```text
k8s/app/overlays/gitops/
```

That overlay is where a generic Kubernetes base becomes GitOps-aware and EKS-aware.

**Figure 3. Repository tree showing the separation between application code, Argo CD control files, and the workload overlay.**

Capture recommendation: Run a folder tree command that clearly shows `apps/`, `argocd/bootstrap`, `argocd/root`, `k8s/app/base`, `k8s/app/overlays/gitops`, and `scripts/`. Crop the output tightly so the reader can see the architecture of the repo at a glance.

## Bootstrapping Argo CD on EKS

Bootstrapping is where GitOps starts feeling real, so it deserves a slow and careful explanation.

### `install-argocd.sh` keeps the control-plane install intentionally small

Start with `scripts/install-argocd.sh`:

```bash
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
```

This script does only three things:

1. create the `argocd` namespace if needed
2. install the Argo CD control plane
3. wait for the server Deployment to become ready

That small scope is a good design choice. The bootstrap path should be easy to reason about.

The `--server-side` flag is intentional here. Recent Argo CD install manifests include large CRDs, and a plain client-side `kubectl apply` can fail with a `metadata.annotations: Too long` error when Kubernetes tries to store the full last-applied configuration as an annotation.

**Figure 4. Bootstrap sequence from shell scripts to the first Argo CD application.**

Nano Banana prompt: Create a clean sequence-style diagram for a lesson. Show a terminal on the left running `install-argocd.sh`, `render-root-app.sh`, and `bootstrap-root-app.sh`. Show those scripts creating the `argocd` namespace, installing Argo CD, rendering the root Application manifest, and applying it to the cluster. Then show Argo CD loading `argocd/root` from Git. Use a white background, clear arrows, and polished engineering-blog styling.

That sequence diagram gives us the mental model. The next step is to watch the first part happen in a real cluster.

At this stage, we are not asking Argo CD to manage the workload yet. We are only making sure the GitOps control plane itself is installed cleanly and the `argocd-server` deployment is healthy on EKS.

**Figure 5. Terminal output from installing Argo CD into the EKS cluster.**

Capture recommendation: Capture the terminal output from `./scripts/install-argocd.sh`, especially the namespace creation, install apply step, and final rollout success message for `argocd-server`.

### The first `Application` object is tiny on purpose

Now open `argocd/bootstrap/root-application.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform-root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: "__GITOPS_REPO_URL__"
    targetRevision: "__GITOPS_REVISION__"
    path: argocd/root
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

This manifest is small because its job is narrow. It is not trying to describe the entire system. It does one thing:

Point Argo CD at `argocd/root` in the repository.

#### Why each field matters

- `name: platform-root` gives the repo a single top-level application in Argo CD.
- `path: argocd/root` tells Argo CD where the rest of the control-plane declarations live.
- `prune: true` means deleted objects in Git should also disappear from the cluster.
- `selfHeal: true` means manual drift in the cluster should be corrected automatically.

That is the bridge from "Argo CD is installed" to "Git is now driving the cluster."

### We render the root application before applying it

The bootstrap manifest uses placeholders for the Git repository URL and revision. Those placeholders are filled by `scripts/render-root-app.sh`:

```bash
sed \
  -e "s|__GITOPS_REPO_URL__|$GITOPS_REPO_URL|g" \
  -e "s|__GITOPS_REVISION__|$GITOPS_REVISION|g" \
  "$ROOT_DIR/argocd/bootstrap/root-application.yaml"
```

Then `scripts/bootstrap-root-app.sh` applies the rendered result:

```bash
"$ROOT_DIR/scripts/render-root-app.sh" | kubectl apply -f -
```

This is a very teachable pattern:

- keep the reusable manifest in Git
- inject the live repo URL and branch at bootstrap time
- avoid hardcoding one specific fork or branch into the shared lesson repo

Before readers run this step on a live cluster, one practical detail matters:

Argo CD must be able to read the Git repository you point it at. For this lesson, the quickest path is a public GitHub repo, but a private repo works too if you register repository credentials in Argo CD first. If Argo CD cannot read the repo, the root app will stay in an `Unknown` sync state with an error such as `authentication required: Repository not found.`

After this step, Argo CD starts reading the rest of the desired state from Git instead of waiting for more shell commands.

## Inside `argocd/root`: This Is the GitOps Control Plane

Once the root application points to `argocd/root`, the next question is obvious:

What exactly is in that directory, and why is it structured this way?

### `kustomization.yaml` is the table of contents

Start with `argocd/root/kustomization.yaml`:

```yaml
resources:
  - bootstrap-settings-configmap.yaml
  - platform-project.yaml
  - workloads-project.yaml
  - kube-prometheus-stack-app.yaml
  - opentelemetry-collector-app.yaml
  - workload-app.yaml
```

This file is the table of contents for the root layer. It tells Argo CD that the root app manages:

- shared bootstrap settings
- project boundaries
- platform child applications
- the workload child application

Already, that teaches something important. The repo is not only managing the application. It is also managing the supporting platform pieces that help operate the application.

### The bootstrap settings ConfigMap keeps shared values in one place

Open `argocd/root/bootstrap-settings-configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-bootstrap-settings
  namespace: argocd
data:
  gitopsRepoUrl: "https://github.com/your-org/argocd-gitops-security-observability-eks.git"
  gitopsRevision: "main"
  kubePrometheusChartVersion: "69.8.2"
  otelCollectorChartVersion: "0.111.1"
```

This is a small file, but it carries an important design idea.

Instead of repeating the Git repo URL or Helm chart versions across multiple `Application` and `AppProject` objects, the repo centralizes them here and then uses Kustomize replacements to inject them where needed.

That is not just cosmetic. It makes the root layer easier to audit and easier to customize for a real fork.

### `AppProject` boundaries make the repo easier to reason about

Argo CD `AppProject` objects are one of the most useful beginner concepts in this repo because they create visible responsibility boundaries.

From `argocd/root/platform-project.yaml`:

```yaml
spec:
  sourceRepos:
    - https://github.com/your-org/placeholder.git
    - https://prometheus-community.github.io/helm-charts
    - https://open-telemetry.github.io/opentelemetry-helm-charts
  destinations:
    - namespace: observability
      server: https://kubernetes.default.svc
```

From `argocd/root/workloads-project.yaml`:

```yaml
spec:
  description: Application and workload-layer resources managed through Argo CD.
  sourceRepos:
    - https://github.com/your-org/placeholder.git
  destinations:
    - namespace: gitops-demo
      server: https://kubernetes.default.svc
```

#### What these project files are really expressing

- the `platform` project is allowed to pull from the repo plus approved Helm chart sources
- the `platform` project is allowed to land in `observability`
- the `workloads` project is allowed to deploy the application into `gitops-demo`

That means the repo is not only declaring resources. It is also declaring where those resources are allowed to come from and where they are allowed to land.

For beginners, that is a healthy introduction to the idea that Argo CD can enforce structure, not just perform syncs.

### The child workload application contains the policy that matters most

Now look at `argocd/root/workload-app.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: workload
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  project: workloads
  source:
    repoURL: https://github.com/your-org/placeholder.git
    targetRevision: main
    path: k8s/app/overlays/gitops
  destination:
    server: https://kubernetes.default.svc
    namespace: gitops-demo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    retry:
      limit: 10
      backoff:
        duration: 15s
        factor: 2
        maxDuration: 3m
    syncOptions:
      - CreateNamespace=true
      - SkipDryRunOnMissingResource=true
```

This file is where the control-plane design becomes concrete.

#### The important fields to notice

- `path: k8s/app/overlays/gitops` makes the overlay the real workload source of truth
- `namespace: gitops-demo` gives the app a dedicated target namespace
- `prune` and `selfHeal` give the app a true GitOps posture
- `retry` makes the first sync more forgiving when platform dependencies are still settling
- `CreateNamespace=true` lets Argo CD create the target namespace if it is not present yet

#### Why `SkipDryRunOnMissingResource=true` deserves extra attention

This flag matters most on first reconciliation.

The workload overlay includes a `ServiceMonitor`, but `ServiceMonitor` is a custom resource defined by the Prometheus Operator stack. That CRD arrives from the `kube-prometheus-stack` application in an earlier sync wave.

Without `SkipDryRunOnMissingResource=true`, Argo CD can dry-run the workload app before that CRD has been registered and fail validation with a "resource type not found" style error. With the flag enabled, Argo CD can keep moving while the platform layer finishes installing the CRD.

That is exactly the kind of small YAML detail that makes a repo feel production-minded instead of decorative.

### Kustomize replacements wire the root layer together

The root `kustomization.yaml` does more than list resources. It also performs targeted replacements:

```yaml
replacements:
  - source:
      kind: ConfigMap
      name: argocd-bootstrap-settings
      fieldPath: data.gitopsRepoUrl
    targets:
      - select:
          kind: AppProject
          name: platform
        fieldPaths:
          - spec.sourceRepos.0
      - select:
          kind: AppProject
          name: workloads
        fieldPaths:
          - spec.sourceRepos.0
      - select:
          kind: Application
          name: workload
        fieldPaths:
          - spec.source.repoURL
```

That is worth calling out because it shows Kustomize doing real configuration work:

- one source value
- several precise targets
- fewer copy-paste mistakes

### Sync waves make the app-of-apps pattern readable

The child applications are deliberately ordered:

- `kube-prometheus-stack`: wave `0`
- `otel-collector`: wave `1`
- `workload`: wave `2`

That gives the repo a human-readable order of operations:

1. install shared metrics infrastructure
2. install the trace collector
3. install the application workload that depends on them

**Figure 6. App-of-apps layout for the Argo CD root application.**

Nano Banana prompt: Create a clean app-of-apps architecture diagram for an Argo CD lesson. Show a root Application labeled `platform-root` at the top. Under it, show three child Applications labeled `kube-prometheus-stack`, `otel-collector`, and `workload`. Add small sync-wave labels `0`, `1`, and `2`. Show that the platform apps land in an `observability` namespace and the workload app lands in a `gitops-demo` namespace. Use a white background, precise arrows, modern flat engineering style, and highly readable labels.

**Figure 7. Argo CD application list after the root application has reconciled.**

Capture recommendation: Prefer the Argo CD UI application list after the root app has reconciled. Make sure the screenshot shows `platform-root`, `kube-prometheus-stack`, `otel-collector`, and `workload` together with their sync and health states.

This is the moment when the app-of-apps idea stops being abstract. In the UI, readers should be able to see one parent application and its child applications all converging on the desired state from Git.

On a fresh cluster, `kube-prometheus-stack` may briefly show `Missing`, `OutOfSync`, or `Syncing` during its first reconciliation. That application installs Prometheus Operator CRDs and then creates resources that depend on them. This repo uses `SkipDryRunOnMissingResource=true` where needed so Argo CD can move through that short CRD registration window instead of treating it as a hard failure, and `ServerSideApply=true` so the large Prometheus Operator CRDs are applied more reliably.

The helper script `scripts/verify-argocd-apps.sh` gives the lesson a nice terminal companion to the UI by collecting:

- `kubectl get applications -n argocd`
- `kubectl get appprojects -n argocd`
- `kubectl get pods -n argocd`

That helps readers verify the control plane even if they are not using the UI yet.

## How the Workload Overlay Becomes a GitOps Target

The root layer tells Argo CD what to manage. The workload overlay tells Argo CD what the application should actually look like in the cluster.

### The base-plus-overlay structure still does useful work

The repo still uses a base plus overlay model because that is the cleanest way to teach reuse.

The base manifests under `k8s/app/base` describe the workload itself:

- API Deployment and Service
- worker Deployment
- Postgres StatefulSet and Services
- migration Job
- shared ConfigMap and Secret
- base Ingress

Then `k8s/app/overlays/gitops` adds the operating model around that workload.

### The overlay `kustomization.yaml` tells you exactly what changes for GitOps on EKS

Open `k8s/app/overlays/gitops/kustomization.yaml`:

```yaml
resources:
  - ../../base
  - gitops-settings-configmap.yaml
  - serviceaccounts.yaml
  - storageclass-gp3.yaml
  - rbac.yaml
  - networkpolicies.yaml
  - service-monitor.yaml

patches:
  - path: patch-api-serviceaccount.yaml
  - path: patch-worker-serviceaccount.yaml
  - path: patch-postgres-storage.yaml
  - path: patch-ingress-alb.yaml
  - path: patch-api-observability.yaml
  - path: patch-worker-observability.yaml
  - path: patch-sync-waves.yaml
```

This single file is one of the best teaching surfaces in the repo because it explains, almost line by line, what the overlay is adding:

- centralized runtime settings
- service accounts for AWS identity
- EBS storage tuning
- RBAC
- network policy
- Prometheus discovery
- observability environment variables
- Argo CD hook behavior

### One ConfigMap drives the values readers change most often

The file `k8s/app/overlays/gitops/gitops-settings-configmap.yaml` centralizes the values readers will edit first:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitops-settings
  namespace: gitops-demo
data:
  apiImage: "123456789012.dkr.ecr.us-east-1.amazonaws.com/gitops-demo-api:latest"
  workerImage: "123456789012.dkr.ecr.us-east-1.amazonaws.com/gitops-demo-worker:latest"
  migratorImage: "123456789012.dkr.ecr.us-east-1.amazonaws.com/gitops-demo-migrator:latest"
  apiRoleArn: "arn:aws:iam::123456789012:role/gitops-demo-api-irsa"
  workerRoleArn: "arn:aws:iam::123456789012:role/gitops-demo-worker-irsa"
  apiHost: "api.example.com"
```

That is a strong repo design choice because it prevents readers from hunting through several manifests just to update image names, IAM role ARNs, or the ingress hostname.

### The migration Job is deliberately converted into a sync hook

One of the most instructive files in the overlay is `k8s/app/overlays/gitops/patch-sync-waves.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: migrate
  namespace: gitops-demo
  annotations:
    argocd.argoproj.io/hook: Sync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation,HookSucceeded
    argocd.argoproj.io/sync-wave: "1"
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api
  namespace: gitops-demo
  annotations:
    argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
    argocd.argoproj.io/sync-wave: "3"
```

#### Why this Job treatment is better than a plain declarative Job

Jobs are not long-running workloads. They are supposed to run to completion. If you manage them carelessly in GitOps, they can become awkward because Kubernetes treats completed Jobs differently from Deployments.

By turning the migration Job into a sync hook, the repo gets cleaner behavior:

- the migration runs as part of the sync flow
- successful runs can be cleaned up
- future syncs can recreate the Job cleanly when needed

That is much closer to how teams actually want schema migrations to behave.

### Render the final workload before asking Argo CD to sync it

The repo includes `scripts/render-workload.sh`:

```bash
kubectl kustomize "$ROOT_DIR/k8s/app/overlays/gitops"
```

This is a habit worth teaching explicitly. Before you let Argo CD reconcile a workload, you should be able to render the exact manifest set and inspect it.

That reduces mystery, makes overlays easier to trust, and gives readers a direct bridge between repo structure and final Kubernetes objects.

**Figure 8. How the GitOps overlay customizes the shared Kubernetes base for EKS.**

Nano Banana prompt: Create a layered Kustomize diagram for a technical lesson. Show `k8s/app/base` at the bottom with generic workload resources. Above it, show `k8s/app/overlays/gitops` adding image replacements, IRSA service accounts, ALB ingress settings, `gp3` storage, RBAC, network policies, observability patches, and Argo CD sync-wave annotations. Show the final rendered output feeding into the `workload` Argo CD Application. Use clean arrows, a white background, flat vector shapes, and clear labels suitable for an engineering blog.

**Figure 9. Rendered output of the GitOps workload overlay before cluster sync.**

Capture recommendation: Run `./scripts/render-workload.sh` or `kubectl kustomize k8s/app/overlays/gitops` and capture a terminal screenshot that clearly shows the namespace, service accounts, Deployments, migration Job hook annotations, and ingress shape.

## The Day-2 Workflow Is the Real Payoff

A GitOps lesson is not finished when the first sync works. The real test is whether the repo teaches a clean day-2 operating model.

### A normal change should start in Git, not in the cluster

Imagine the API image changes.

In a manual workflow, someone might patch the Deployment directly in the cluster. In this repo, the cleaner path is:

1. update `apiImage` in `k8s/app/overlays/gitops/gitops-settings-configmap.yaml`
2. commit and push that change
3. let Argo CD detect that the workload is `OutOfSync`
4. let Argo CD reconcile the cluster to the new desired state
5. verify that the new API pods roll out successfully

The key lesson is not the image tag itself. The key lesson is where the change happens.

The change starts in Git. The cluster follows afterward.

### A concrete image-update example makes the flow visible

An image update might look as small as this:

```yaml
data:
  apiImage: "123456789012.dkr.ecr.us-east-1.amazonaws.com/gitops-demo-api:2026-06-24"
```

That small edit is enough to teach the core GitOps idea:

- Git changes first
- Argo CD notices the difference
- the application becomes `OutOfSync`
- a sync brings the live cluster back to the declared state

In a real team, this Git change is often written automatically by Argo CD Image Updater or by a CI job that updates the tag and commits it back to the repo. In this lesson, we keep the tag update manual because it makes the flow visible to the reader.

### Rollback should follow the same path as rollout

The rollback story should match the rollout story.

The cleanest rollback is usually:

1. revert the commit that changed the image
2. push the revert
3. let Argo CD detect the drift
4. let Argo CD reconcile back to the last known-good state

Argo CD also supports direct rollback commands:

```bash
argocd app rollback workload
```

That can be useful operationally, but for teaching purposes, Git revert is the better primary story because it keeps the declared source of truth consistent with what the cluster is doing.

### Verification should be part of the workflow, not an afterthought

After a sync or rollback, `scripts/verify-argocd-apps.sh` gives readers a compact verification path:

```bash
kubectl get applications -n argocd
kubectl get appprojects -n argocd
kubectl get pods -n argocd
```

That is small, but it is valuable. It gives the lesson both a UI-based and a terminal-based way to prove that GitOps is working.

**Figure 10. Day-2 GitOps flow from Git commit to Argo CD-driven rollout.**

Nano Banana prompt: Create a clear step-by-step GitOps change diagram for a Kubernetes lesson. Show a developer updating the `apiImage` value in Git, committing and pushing the change, Argo CD detecting `OutOfSync`, Argo CD syncing the cluster, and new API pods rolling out on Amazon EKS. Add small status labels `OutOfSync` and `Synced` at the right moments. Use polished engineering-blog styling, simple arrows, and clear readable labels.

**Figure 11. Argo CD application detail page showing the workload as healthy and synced.**

Capture recommendation: Capture the Argo CD application detail page for `workload` after a successful sync. Make sure the screenshot shows the `Healthy` and `Synced` status plus enough of the resource tree for readers to recognize the API, worker, migration Job, and Postgres resources.

Between the app list and the application detail page, readers can see both the high-level control plane and the workload-level reconciliation story.

**Figure 12. Argo CD showing the workload as out of sync during a day-2 change.**

Capture recommendation: Capture the Argo CD UI or `kubectl get applications -n argocd` during a change where the workload shows `OutOfSync` or is mid-sync. Make sure the screenshot makes the day-2 GitOps idea concrete instead of purely theoretical.

## What Readers Actually Learn From This Repo

At the beginning of the lesson, Argo CD can look like just one more tool in the Kubernetes stack.

By the end, the value should feel much broader than that.

### Git becomes the operational surface

The most important lesson is not a particular command. It is a healthier operating model:

- Git stores the desired state
- Argo CD reconciles that state into the cluster
- the repo becomes the control surface for day-2 operations

That is a much stronger mental model than "apply some YAML and hope we remember what changed later."

### Cluster changes become reviewable and repeatable

Once deployment changes move into Git, they become:

- reviewable
- reproducible
- rollback-friendly
- easier for a team to understand

That is one of the biggest differences between a demo deployment and a production-minded workflow.

### The next layer becomes easier to add

Once delivery is clean, the next question becomes easier to ask:

How do we make the workload safer to run and easier to observe?

That is exactly where the next lesson picks up.

## Conclusion

This lesson is not about inventing a new Kubernetes application. It is about making a familiar application sustainable on Amazon EKS.

We bootstrapped Argo CD into the cluster, used a tiny root application to hand control to Git, structured the repo around an app-of-apps pattern, and shaped the workload overlay into a proper GitOps target.

That is the real teaching win.

Readers leave with a much more mature idea of Kubernetes operations:

- deployment state belongs in Git
- Argo CD should reconcile the cluster to that state
- day-2 changes and rollbacks should follow the same Git-first workflow

In the next lesson, we will build directly on this foundation. The same `workload` application that Argo CD syncs here will also carry the `ServiceAccount`, `RBAC`, `NetworkPolicy`, `ServiceMonitor`, and OpenTelemetry wiring that make the namespace safer and easier to operate.

That is why these two lessons belong together. First we make delivery Git-driven. Then we make that Git-driven state secure and observable.
