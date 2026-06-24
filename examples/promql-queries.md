# PromQL starter queries

Use these as starter queries once Prometheus is scraping the `api` service in the `gitops-demo` namespace.

## Request rate

```promql
sum(rate(http_requests_total{job="api"}[5m]))
```

## Request duration p95

```promql
histogram_quantile(
  0.95,
  sum(rate(http_request_duration_seconds_bucket{job="api"}[5m])) by (le)
)
```

## In-flight requests

```promql
sum(http_requests_inprogress{job="api"})
```

## Target health

```promql
up{namespace="gitops-demo"}
```
