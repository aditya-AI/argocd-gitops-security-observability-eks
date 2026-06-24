from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_TRACING_CONFIGURED = False


def _trace_export_endpoint() -> str:
    raw = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not raw:
        return ""
    if raw.endswith("/v1/traces"):
        return raw
    return f"{raw.rstrip('/')}/v1/traces"


def configure_observability() -> None:
    global _TRACING_CONFIGURED

    endpoint = _trace_export_endpoint()
    if not endpoint or _TRACING_CONFIGURED:
        return

    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "gitops-demo-worker"),
            "deployment.environment": os.getenv("DEPLOY_ENV", "eks"),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    LoggingInstrumentor().instrument(set_logging_format=True)
    PsycopgInstrumentor().instrument()
    _TRACING_CONFIGURED = True


def get_tracer(name: str):
    return trace.get_tracer(name)
