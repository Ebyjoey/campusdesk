def test_health_and_ready(app):
    client = app.test_client()
    assert client.get("/healthz").get_json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 200


def test_metrics_exposed(make_client, ticket):
    client = make_client("admin@t.io")
    client.get("/api/complaints")
    text = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_total" in text
    assert "http_request_duration_seconds_bucket" in text
    assert 'campusdesk_complaints_created_total{category="Hostel"}' in text
    assert 'campusdesk_complaints_open{status="Open"} 1.0' in text


def test_unknown_api_path_is_json_404(app):
    res = app.test_client().get("/api/nope")
    assert res.status_code == 404 and res.get_json()["error"]


def test_admin_pages(make_client):
    admin = make_client("admin@t.io")
    assert admin.get("/admin/categories").status_code == 200
    assert make_client("student@t.io").get("/admin/categories").status_code == 403


def test_detail_page_renders_for_each_role(make_client, ticket):
    assert make_client("student@t.io").get(f"/complaints/{ticket}").status_code == 200
    assert make_client("admin@t.io").get(f"/complaints/{ticket}").status_code == 200
    assert make_client("staff@t.io").get(f"/complaints/{ticket}").status_code == 404
