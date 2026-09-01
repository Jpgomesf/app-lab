"""OpenTelemetry wiring.

Entirely opt-in. With OTEL_EXPORTER_OTLP_ENDPOINT unset, `main` never imports
this module, so the grpc exporter stack is not loaded, no provider is installed
and a local run with no collector makes no export attempts.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from api.config import Settings

logger = logging.getLogger(__name__)

# Probes fire every few seconds and carry no diagnostic value as spans.
_EXCLUDED_URLS = "healthz,readyz"


def configure_tracing(app: FastAPI, settings: Settings) -> TracerProvider | None:
    """Install a tracer provider and instrument the app, if configured.

    Returns the provider so the lifespan can shut it down (flushing the batch
    processor) on the way out; `None` when tracing is off.
    """
    endpoint = settings.otel_exporter_otlp_endpoint
    if endpoint is None:
        return None

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    # `http://` in the endpoint means plaintext; the collector in the lab is
    # in-cluster on 4317 with no TLS.
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))
        )
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=_EXCLUDED_URLS)
    logger.info("tracing enabled", extra={"event": "tracing_enabled", "endpoint": endpoint})
    return provider
