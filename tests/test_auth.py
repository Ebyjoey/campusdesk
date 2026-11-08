def test_register_login_me_logout(app):
    client = app.test_client()
    res = client.post(
        "/api/auth/register",
        json={"name": "New Kid", "email": "New@Kid.io", "password": "longenough1"},
    )
    assert res.status_code == 201
    assert res.get_json()["role"] == "student"

    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "new@kid.io", "password": "longenough1"}).status_code == 200
    assert client.get("/api/auth/me").get_json()["email"] == "new@kid.io"
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_register_validation_and_duplicates(app):
    client = app.test_client()
    assert client.post("/api/auth/register", json={"name": "A", "email": "x@y.io", "password": "longenough1"}).status_code == 400
    assert client.post("/api/auth/register", json={"name": "Alice", "email": "nope", "password": "longenough1"}).status_code == 400
    assert client.post("/api/auth/register", json={"name": "Alice", "email": "a@b.io", "password": "short"}).status_code == 400
    res = client.post("/api/auth/register", json={"name": "Dup", "email": "student@t.io", "password": "longenough1"})
    assert res.status_code == 409


def test_password_is_hashed(app):
    from app.models import User

    with app.app_context():
        user = User.query.filter_by(email="student@t.io").first()
        assert user.password_hash != "Passw0rd!"
        assert user.check_password("Passw0rd!")
        assert not user.check_password("wrong")


def test_bad_login_counts_failure_metric(app):
    client = app.test_client()
    res = client.post("/api/auth/login", json={"email": "student@t.io", "password": "bad"})
    assert res.status_code == 401
    metrics = client.get("/metrics").get_data(as_text=True)
    assert "campusdesk_login_failures_total" in metrics


def test_html_login_and_dashboard(app):
    client = app.test_client()
    res = client.post("/login", data={"email": "student@t.io", "password": "Passw0rd!"})
    assert res.status_code == 302
    assert client.get("/dashboard").status_code == 200
    assert client.get("/complaints").status_code == 200
    assert client.get("/complaints/new").status_code == 200


def test_pages_require_login(app):
    client = app.test_client()
    res = client.get("/dashboard")
    assert res.status_code == 302 and "/login" in res.headers["Location"]
