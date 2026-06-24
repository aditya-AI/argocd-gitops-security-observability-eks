# Securing and Observing Kubernetes Workloads on Amazon EKS

In the previous lesson, we moved this workload onto a GitOps operating model. We installed Argo CD, bootstrapped a root application, used the app-of-apps pattern to manage platform components and the workload, and let Git become the source of truth for what should run on Amazon EKS.

Once that foundation is in place, the next question becomes more interesting:

Is the namespace actually safe to run, and can we tell what the application is doing when things go wrong?

That is the focus of this lesson.

The application itself stays the same familiar shape:

- an `api` service
- a `worker` service
- a one-shot `migrator` Job
- a `postgres` database

Argo CD is already reconciling the repo. That matters because it means the security rules and observability wiring we add here are not side work done manually in the cluster. They are part of the same repo-driven story.

So this lesson is a continuation, not a reset:

- the same `workload` Argo CD application is still managing `k8s/app/overlays/gitops`
- the same `gitops-demo` namespace is still hosting the application
- the same root layer is still installing the Prometheus and OpenTelemetry platform pieces
- the difference now is that we look deeper at the workload overlay and explain the resources that harden and instrument it

By the end of this lesson, readers should understand:

- why GitOps alone is not enough for a production-minded EKS workflow
- how dedicated service accounts, IRSA, and RBAC make namespace access more intentional
- how a default-deny `NetworkPolicy` posture maps directly onto the application topology
- why the current plain Kubernetes Secret is only a transitional step
- how metrics and traces are wired through both application code and Kubernetes manifests
- what to verify in a live cluster once the workload is healthy

One small first-sync wrinkle is worth calling out early. The `kube-prometheus-stack` application creates Prometheus Operator CRDs and then immediately creates resources such as `PrometheusRule` and `ServiceMonitor` that depend on those CRDs. During that first reconciliation, Argo CD can briefly show `Missing`, `OutOfSync`, or `Syncing` states while the Kubernetes API registers those custom resource types. That short-lived noise is normal. In this repo, we explicitly enable the chart CRDs, turn on the chart's CRD upgrade job, set `SkipDryRunOnMissingResource=true` so Argo CD keeps moving instead of failing the sync on CRD timing, and use `ServerSideApply=true` because the Prometheus Operator CRDs are large enough that client-side apply can become fragile.

**Figure 1. Security and observability architecture for the workload on Amazon EKS.**

Nano Banana prompt: Create a polished engineering-blog architecture diagram on a white background. Show the `gitops-demo` namespace containing `api`, `worker`, `migrator`, and `postgres`. Surround the namespace with a subtle `default deny` security boundary. Show `api-sa` and `worker-sa` using IRSA. Show Prometheus scraping `/metrics` from the API. Show both `api` and `worker` sending OTLP traces to an OpenTelemetry Collector in the `observability` namespace. Use clean blue-gray cloud colors, crisp labels, and a modern lesson-ready visual style.

## Why GitOps Is Necessary but Still Not Sufficient

GitOps gives us a better delivery model. It does not automatically give us a better runtime posture.

That distinction matters, and it is exactly why this lesson exists as the second half of the module.

If all we did was install Argo CD and sync manifests from Git, we would still be leaving important questions unanswered:

- which workloads should have AWS permissions
- which identities should be allowed to inspect or operate the namespace
- which network paths should exist between Pods
- whether Prometheus is really scraping the API
- whether the worker is really emitting traces during job processing

Those are operational questions, not optional extras.

### The goal here is safer defaults, not maximum complexity

This lesson is not trying to build a perfect zero-trust platform in one shot. That would be too much for a single lesson.

Instead, it aims for a realistic first layer:

- dedicated service accounts
- narrower RBAC
- explicit network flows
- visible metrics
- visible traces

That is exactly the right scope for a teaching repo because it shows how to improve the posture of a namespace without disappearing into enterprise policy machinery.

## Identity and Access: Make the Namespace More Intentional

The security work in this repo lives mostly in `k8s/app/overlays/gitops/`. That is a good sign. It means the hardening decisions are captured in Git instead of being applied as one-off cluster surgery.

### Dedicated service accounts are the first identity boundary

Start with `k8s/app/overlays/gitops/serviceaccounts.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-sa
  namespace: gitops-demo
  annotations:
    eks.amazonaws.com/role-arn: "replace-me"
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: worker-sa
  namespace: gitops-demo
  annotations:
    eks.amazonaws.com/role-arn: "replace-me"
```

This file teaches two useful habits immediately:

- the API and worker do not share the default namespace service account
- AWS access, if the workloads need it, should be attached through IRSA instead of static credentials

#### Why the annotation still says `replace-me`

The repo does not hardcode one IAM role ARN into version control. Instead, the real ARNs are injected from `k8s/app/overlays/gitops/gitops-settings-configmap.yaml` through Kustomize replacements.

That gives readers a better pattern:

- keep the service account intent in YAML
- keep the environment-specific ARN in a central settings file
- let Kustomize wire the final value into the manifest

Even though this demo does not need broad AWS permissions yet, that identity pattern is worth learning early.

### RBAC makes namespace access feel deliberate instead of accidental

Now open `k8s/app/overlays/gitops/rbac.yaml`.

This file introduces two simple roles that are easy to explain and realistic enough to teach:

- `app-readonly`
- `app-operator`

Here is the read-only side:

```yaml
kind: Role
metadata:
  name: app-readonly
  namespace: gitops-demo
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "services", "endpoints", "events", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets"]
    verbs: ["get", "list", "watch"]
```

And here is the broader operator role:

```yaml
kind: Role
metadata:
  name: app-operator
  namespace: gitops-demo
rules:
  - apiGroups: ["apps"]
    resources: ["deployments", "deployments/scale", "statefulsets", "statefulsets/scale"]
    verbs: ["get", "list", "watch", "patch", "update"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["get", "list", "watch", "patch", "update", "create", "delete"]
```

#### What this RBAC split teaches

- some identities only need to inspect the namespace
- some identities need limited operational power
- not every user or service account should have the same verbs on the same resources

For beginners, that mindset matters more than memorizing every Kubernetes RBAC field.

**Figure 2. Namespace security model showing identity boundaries and allowed traffic.**

Nano Banana prompt: Create a clean security-focused diagram for a Kubernetes lesson. Show the `gitops-demo` namespace with `api`, `worker`, `migrator`, and `postgres` pods. Add a `default deny` shield around the namespace. Then show only the allowed flows: external traffic to the API, API and worker to Postgres, migrator to Postgres, and API plus worker traces to the `observability` namespace. Add callouts for `IRSA`, `RBAC`, and `NetworkPolicy`. Use a white background, modern flat vector styling, and clear labels.

**Figure 3. Verifying service accounts, RBAC, and network policies in the workload namespace.**

Capture recommendation: Capture a terminal view that includes `kubectl get sa,role,rolebinding,networkpolicy -n gitops-demo`. Make sure the screenshot shows `api-sa`, `worker-sa`, `app-readonly`, `app-operator`, and the network policies together.

The helper script `scripts/verify-security-observability.sh` is especially useful here because it groups the namespace checks into one repeatable command instead of leaving the lesson with a pile of one-off verification snippets.

## NetworkPolicy: Express the Application Topology as Rules

`NetworkPolicy` often feels abstract when readers meet it in isolation. In this repo, it becomes much easier to understand because it maps directly onto an application the reader already knows.

### The first rule is a namespace-wide default deny

Open `k8s/app/overlays/gitops/networkpolicies.yaml` and look at the first resource:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: gitops-demo
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

This is a powerful teaching moment because it changes the default assumption of the namespace:

Pods should not assume open network access by default.

That one policy alone teaches a stronger security posture than many introductory Kubernetes lessons ever reach.

### Then the file opens only the paths the app actually needs

From there, the overlay adds narrowly scoped allow rules.

For example, the API is allowed to reach Postgres and the observability namespace:

```yaml
kind: NetworkPolicy
metadata:
  name: allow-api-egress
  namespace: gitops-demo
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: observability
      ports:
        - protocol: TCP
          port: 4318
```

And Postgres is allowed to accept traffic only from the application components that truly need it:

```yaml
kind: NetworkPolicy
metadata:
  name: allow-postgres-ingress
  namespace: gitops-demo
spec:
  podSelector:
    matchLabels:
      app: postgres
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api
        - podSelector:
            matchLabels:
              app: worker
        - podSelector:
            matchLabels:
              app: migrator
      ports:
        - protocol: TCP
          port: 5432
```

#### Why the migrator rule deserves explicit attention

This is one of the practical details many lessons skip.

Once you adopt default deny, the migration Job also needs a legitimate path to reach Postgres. That is why the overlay includes `allow-migrator-egress`, and why Postgres ingress explicitly allows traffic from Pods labeled `app: migrator`.

This is where the policy stops feeling theoretical. The rules are expressing the real topology of the application:

- external traffic reaches the API
- the API and worker reach Postgres
- the migrator reaches Postgres
- the API and worker can export traces

### The network policy file also explains the observability design

Notice that the API and worker are allowed to reach the `observability` namespace on port `4318`. That is not random. It is the OTLP HTTP port used by the OpenTelemetry Collector in this repo.

So even the network policy file is telling part of the observability story.

## Secrets: Be Honest About the Transitional Step and Show the Next One

This repo still includes a plain Kubernetes Secret in `k8s/app/base/secret.yaml`.

That is acceptable for teaching because it keeps the main path understandable, but it is also the right place to be honest with readers:

This is not where a production secret story should stop.

### The current Secret keeps the main lesson readable

Using a basic Kubernetes Secret here does one useful thing for the lesson. It keeps the application manifests straightforward while we focus on GitOps, namespace hardening, and telemetry.

That is a reasonable trade-off for a lesson.

### The next production-minded step is already shown in the repo

The repo includes `examples/external-secret.yaml` as the next-step pattern:

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: app-secret
  namespace: gitops-demo
spec:
  secretStoreRef:
    name: aws-store
    kind: SecretStore
  target:
    name: app-secret
  data:
    - secretKey: DB_PASSWORD
      remoteRef:
        key: gitops-demo/database
        property: password
```

This is a valuable bridge for readers because it shows a cleaner future state without dragging the entire lesson into operator installation and cloud secret plumbing.

The important idea is simple:

- the application can still consume a normal Kubernetes Secret
- the real secret value can come from AWS Secrets Manager
- Git no longer needs to be the place where the secret itself lives

**Figure 4. External Secrets pattern for moving database credentials out of Git.**

Nano Banana prompt: Create a clean cloud-native architecture diagram on a white background. Show AWS Secrets Manager on the left storing a database password. Show External Secrets Operator synchronizing that secret into the `gitops-demo` namespace as a Kubernetes Secret named `app-secret`. Show the API, worker, and migrator consuming that Secret. Use modern flat vector styling, clear labels, and a lesson-friendly engineering aesthetic.

## Observability in Application Code

Observability becomes much less intimidating when readers can see that a few focused code changes unlock most of the first useful signals.

### The API exposes Prometheus metrics directly

Open `apps/api/app/observability.py`:

```python
if not _METRICS_CONFIGURED:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    _METRICS_CONFIGURED = True
```

This is a good teaching choice because it does not force the reader to write a custom metrics library just to get started. It exposes Prometheus-friendly metrics on `/metrics` so the platform can scrape them.

Then in `apps/api/app/main.py`, observability is enabled as part of app startup:

```python
app = FastAPI(title="gitops-demo-api", lifespan=lifespan)
configure_observability(app)
```

That tells the reader something important:

Observability is not a bolt-on shell script. It starts inside the application process.

### The API also wires in OpenTelemetry tracing

From the same `observability.py` module:

```python
resource = Resource.create(
    {
        "service.name": os.getenv("OTEL_SERVICE_NAME", "gitops-demo-api"),
        "deployment.environment": os.getenv("DEPLOY_ENV", "eks"),
        "service.version": os.getenv("APP_VERSION", "v1"),
    }
)
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
trace.set_tracer_provider(provider)
```

There are two big ideas in that block:

- the service name and environment are attached to spans as resource attributes
- the application does not hardcode a tracing backend; it exports to a configurable OTLP endpoint

That is exactly the kind of portability we want in a repo like this.

### The worker emits spans around real work, not fake demo events

The worker side is just as important. In `apps/worker/worker/main.py`, the processing loop is wrapped in a span:

```python
with tracer.start_as_current_span("worker.run_once") as span:
    ...
    if row is None:
        span.set_attribute("worker.job_found", False)
        return False

    (job_id,) = row
    span.set_attribute("worker.job_found", True)
    span.set_attribute("worker.job_id", str(job_id))
```

This is a strong example because the lesson is not inventing lesson-only spans. It is instrumenting a real unit of application behavior: the worker polling for jobs and processing them.

That makes the trace data meaningful.

## Observability in the Kubernetes Layer

Application code is only half of the observability story. The cluster still needs to tell those processes where to send telemetry and how to expose metrics to the platform.

### The overlay injects the OTEL runtime configuration

The file `k8s/app/overlays/gitops/patch-api-observability.yaml` adds environment variables to the API Deployment:

```yaml
env:
  - name: DEPLOY_ENV
    value: "eks"
  - name: OTEL_SERVICE_NAME
    value: "gitops-demo-api"
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-collector.observability.svc.cluster.local:4318"
  - name: OTEL_RESOURCE_ATTRIBUTES
    value: "service.namespace=gitops-demo,deployment.environment=eks"
```

The worker patch mirrors the same pattern in `patch-worker-observability.yaml`.

That teaches a clean separation of responsibilities:

- application code knows how to emit telemetry
- the overlay tells the application where the collector lives in this environment

### Prometheus discovers the API through a `ServiceMonitor`

The API metrics endpoint becomes useful once Prometheus knows how to find it. That is the role of `k8s/app/overlays/gitops/service-monitor.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api
  namespace: gitops-demo
  labels:
    release: kube-prometheus-stack
spec:
  selector:
    matchLabels:
      app: api
  namespaceSelector:
    matchNames:
      - gitops-demo
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

This is a realistic and production-adjacent pattern:

- the API Service exposes a named port
- the `ServiceMonitor` selects the Service by label
- Prometheus automatically discovers and scrapes `/metrics`

The repo also includes `examples/promql-queries.md`, which gives readers a few starter queries once the target is live.

### The root layer still installs the supporting platform services

The workload overlay adds the application-facing hooks, but the supporting platform still needs to exist. That is why the root Argo CD layer also includes:

- `argocd/root/kube-prometheus-stack-app.yaml`
- `argocd/root/opentelemetry-collector-app.yaml`

That design matters because it shows observability is part of the same GitOps-managed platform, not something bolted on later by hand.

In this repo, the collector uses a `debug` exporter. That is actually a smart teaching choice. It gives the lesson visible trace evidence without requiring a full tracing backend such as Jaeger or Tempo in the same module.

**Figure 5. Metrics and trace flow for the workload.**

Nano Banana prompt: Create a clean observability architecture diagram on a white background. Show the `api` service exposing `/metrics` to Prometheus. Show Prometheus feeding Grafana dashboards. Show both `api` and `worker` sending OTLP traces to an OpenTelemetry Collector in the `observability` namespace. Show the collector emitting debug logs for traces. Use crisp engineering labels, simple arrows, and a polished lesson-friendly visual style.

**Figure 6. How observability wiring connects application code, overlay patches, and platform services.**

Nano Banana prompt: Create a clean engineering diagram on a white background that shows three layers from left to right. Layer 1: application code in `apps/api/app/observability.py`, `apps/api/app/main.py`, `apps/worker/worker/observability.py`, and `apps/worker/worker/main.py`. Layer 2: Kubernetes overlay patches injecting `OTEL_SERVICE_NAME`, `DEPLOY_ENV`, and `OTEL_EXPORTER_OTLP_ENDPOINT`, plus the `ServiceMonitor`. Layer 3: platform components `Prometheus`, `Grafana`, and `OpenTelemetry Collector` in the `observability` namespace. Use simple arrows, crisp labels, and polished lesson-ready styling.

**Figure 7. Argo CD resource tree showing security and observability objects under the workload application.**

Capture recommendation: Capture the Argo CD application detail page for `workload` with the resource tree expanded enough to show `NetworkPolicy`, `ServiceAccount`, and `ServiceMonitor` resources alongside the API, worker, Job, and Postgres objects.

That screenshot is useful because it ties the GitOps control plane back to the runtime posture. Readers can see that hardening and telemetry are first-class managed resources, not side notes.

## The Practical Verification Story

Security and observability lessons become much stronger when readers know what proof to look for in a live cluster.

### Start by verifying that the namespace objects exist

The helper script `scripts/verify-security-observability.sh` collects three useful views:

```bash
kubectl get sa,role,rolebinding,networkpolicy,servicemonitor -n gitops-demo
kubectl get pods,svc,ingress,job -n gitops-demo
kubectl get pods -n observability
```

That gives readers a compact terminal verification path instead of scattering the lesson across too many one-off commands.

**Figure 8. Terminal verification of workload security and observability resources.**

Capture recommendation: Capture the output of `./scripts/verify-security-observability.sh` after a healthy sync. Keep the `gitops-demo` resources and the `observability` namespace Pods visible in the same screenshot if possible.

### Then verify the API metrics endpoint directly

Before jumping straight to Prometheus, it helps to prove that the API itself is exposing metrics.

A simple port-forward plus `curl` does that very clearly:

```bash
kubectl -n gitops-demo port-forward svc/api 8080:80
curl http://127.0.0.1:8080/metrics
```

This is a nice bridge between code and platform:

- the application code exposes `/metrics`
- the Kubernetes Service makes it reachable
- Prometheus will later scrape that same endpoint

**Figure 9. Direct verification of the API `/metrics` endpoint.**

Capture recommendation: Port-forward the API service and capture a terminal screenshot of `curl http://127.0.0.1:8080/metrics` showing real Prometheus-formatted metric output from the API.

### Prometheus should then show the API as a healthy scrape target

Once the `ServiceMonitor` and the Prometheus stack are both healthy, the next proof point is target discovery.

This is where `examples/promql-queries.md` becomes useful as a companion to the UI:

- request rate
- request latency
- in-flight requests
- target health

**Figure 10. Prometheus target discovery for the API service.**

Capture recommendation: Capture the Prometheus Targets page or a Prometheus query view that proves the API target is being scraped through the `ServiceMonitor`. If you use the UI, make sure the target is shown as healthy.

### Trace verification comes from the collector logs in this repo

Because this repo does not install a full tracing UI, the simplest proof for traces is the collector's debug output.

That is still a valid teaching surface. It proves the application is exporting spans and the collector is receiving them.

The nicest way to demonstrate it is:

1. create a few jobs through the API
2. let the worker process them
3. inspect the OpenTelemetry Collector logs

**Figure 11. OpenTelemetry Collector logs showing traces from the API or worker.**

Capture recommendation: Capture `kubectl logs` output from the OpenTelemetry Collector after creating a few jobs through the API. Make sure the screenshot clearly shows evidence that spans are being received, not just container startup logs.

### Success should look like several signals agreeing at once

At the end of the exercise, success should mean more than "the cluster did not crash." Readers should be able to confirm all of the following together:

- service accounts and RBAC objects exist
- network policies exist and match the application topology
- workload Pods are healthy
- observability namespace Pods are healthy
- Prometheus is scraping the API
- the collector is receiving spans

**Figure 12. Workload namespace state after security and observability are fully reconciled.**

Capture recommendation: Capture `kubectl -n gitops-demo get pods,svc,ingress,job,servicemonitor` after a healthy sync. Make sure the screenshot includes the API, worker, Postgres, ingress, migration Job status, and `ServiceMonitor`.

## What Readers Really Learn Here

At the beginning of this lesson, security and observability can feel like platform topics that belong somewhere else.

This repo teaches a much healthier idea.

### Platform work is part of application work

A production-minded EKS workflow does not stop at deployment. It also includes:

- workload identity
- namespace access boundaries
- network boundaries
- metrics
- traces

That is why these files belong in the same repository conversation as Deployments and Services.

### Security controls become easier to understand when they match the app

The policies in this repo are not abstract. They map directly onto a workload the reader already understands:

- the API needs ingress
- the API and worker need Postgres
- the migrator needs Postgres
- the API and worker need a path to the observability namespace

That makes `NetworkPolicy` far less intimidating because it is expressing known relationships instead of unfamiliar theory.

### Observability becomes less scary when it is incremental

We do not jump straight into a giant monitoring platform with every possible dashboard and alert. Instead, we add a first useful layer:

- API metrics
- API traces
- worker traces
- Prometheus discovery
- collector visibility

That is a realistic way to teach observability because it shows useful signals appearing early without turning the lesson into a full monitoring course.

## Conclusion

This lesson takes a GitOps-managed workload and gives it a healthier runtime posture on Amazon EKS.

We introduced dedicated service accounts, IRSA-friendly annotations, scoped RBAC, and `NetworkPolicy` rules that default to deny and then open only the traffic the application actually needs. We also wired metrics and traces into both the application code and the Kubernetes overlay so Prometheus and the OpenTelemetry Collector can start telling us what the system is doing.

That is the real win of the second lesson.

Readers leave with a much more professional picture of how a Kubernetes workload should be operated:

- deliver it through Git
- secure it with intentional boundaries
- observe it with metrics and traces

Taken together, the two lessons now tell one complete story:

- first, Argo CD and GitOps make the cluster state reviewable and repeatable
- then, security and observability make that same cluster state safer and easier to understand

Once those three ideas come together, Amazon EKS stops looking like a place where manifests merely run and starts looking like a platform that can actually be managed with confidence.
