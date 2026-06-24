from __future__ import annotations

import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator

_TRACING_CONFIGURED = False
_METRICS_CONFIGURED = False


def _trace_export_endpoint() -> str:
    raw = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not raw:
        return ""
    if raw.endswith("/v1/traces"):
        return raw
    return f"{raw.rstrip('/')}/v1/traces"


def configure_observability(app: FastAPI) -> None:
    global _TRACING_CONFIGURED
    global _METRICS_CONFIGURED

    endpoint = _trace_export_endpoint()
    if endpoint and not _TRACING_CONFIGURED:
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
        LoggingInstrumentor().instrument(set_logging_format=True)
        PsycopgInstrumentor().instrument()
        _TRACING_CONFIGURED = True

    FastAPIInstrumentor.instrument_app(app)

    if not _METRICS_CONFIGURED:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        _METRICS_CONFIGURED = True
