"""Prometheus metrics. Names match the dashboards and PromQL in the project plan."""
import time

from flask import g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter(
    "http_requests_total", "HTTP requests", ["method", "endpoint", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
COMPLAINTS_CREATED = Counter(
    "campusdesk_complaints_created_total", "Complaints created", ["category"]
)
COMPLAINTS_OPEN = Gauge(
    "campusdesk_complaints_open", "Complaints by status (read at scrape time)", ["status"]
)
LOGIN_FAILURES = Counter(
    "campusdesk_login_failures_total", "Failed login attempts"
)

SKIP_ENDPOINTS = {"main.metrics", "static"}


def init_metrics(app):
    @app.before_request
    def _start_timer():
        g._t0 = time.perf_counter()

    @app.after_request
    def _record(response):
        endpoint = request.endpoint or "unmatched"
        if endpoint not in SKIP_ENDPOINTS and hasattr(g, "_t0"):
            REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
            LATENCY.labels(endpoint).observe(time.perf_counter() - g._t0)
        return response


def render_metrics(db, Complaint, STATUSES):
    """Refresh the DB-backed gauge, then return the Prometheus text payload."""
    rows = dict(
        db.session.query(Complaint.status, db.func.count(Complaint.id))
        .group_by(Complaint.status)
        .all()
    )
    for status in STATUSES:
        COMPLAINTS_OPEN.labels(status).set(rows.get(status, 0))
    return generate_latest(), CONTENT_TYPE_LATEST
