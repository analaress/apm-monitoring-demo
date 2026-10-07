import os
import random
import time

from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

app = Flask(__name__)
REQUESTS = Counter("http_requests_total", "Total de requisições HTTP", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Duração das requisições HTTP", ["method", "path"])
PRODUCTS = [
    {"id": 1, "name": "Notebook", "price": 3499.90},
    {"id": 2, "name": "Monitor", "price": 1299.90},
    {"id": 3, "name": "Teclado", "price": 249.90},
]


def setup_telemetry():
    if not OTEL_AVAILABLE or os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        return
    resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "apm-demo-api")})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317"),
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()


setup_telemetry()


@app.before_request
def start_timer():
    request._apm_started_at = time.perf_counter()


@app.after_request
def record_metrics(response):
    path = request.url_rule.rule if request.url_rule else request.path
    elapsed = time.perf_counter() - getattr(request, "_apm_started_at", time.perf_counter())
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(elapsed)
    return response


@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "apm-demo-api"})


@app.get("/produtos")
def products():
    return jsonify({"items": PRODUCTS, "count": len(PRODUCTS)})


@app.get("/checkout")
def checkout():
    """Simulates a checkout dependency for the APM demonstration.

    Query params: delay_ms (0-5000), fail (true/false), external_ms (0-5000).
    """
    delay_ms = min(max(int(request.args.get("delay_ms", "80")), 0), 5000)
    external_ms = min(max(int(request.args.get("external_ms", "120")), 0), 5000)
    should_fail = request.args.get("fail", "false").lower() == "true"
    time.sleep(delay_ms / 1000)

    payment_start = time.perf_counter()
    time.sleep(external_ms / 1000)
    payment_ms = round((time.perf_counter() - payment_start) * 1000, 2)

    if should_fail:
        return jsonify({
            "status": "failed",
            "error": "payment_provider_timeout",
            "payment_dependency_ms": payment_ms,
        }), 504

    return jsonify({
        "status": "approved",
        "order_id": f"ORD-{random.randint(10000, 99999)}",
        "payment_dependency_ms": payment_ms,
    })


@app.errorhandler(ValueError)
def invalid_parameter(error):
    return jsonify({"error": "invalid_parameter", "message": str(error)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
