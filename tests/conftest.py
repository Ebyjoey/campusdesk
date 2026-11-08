import pytest

from app import create_app
from app.extensions import db
from app.models import Category, User


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
            "SECRET_KEY": "test",
        }
    )
    with app.app_context():
        db.create_all()
        for name in ("Hostel", "Wi-Fi / Network"):
            db.session.add(Category(name=name, default_department="Test"))
        for name, email, role in [
            ("Admin", "admin@t.io", "admin"),
            ("Staff", "staff@t.io", "staff"),
            ("Other Staff", "staff2@t.io", "staff"),
            ("Student", "student@t.io", "student"),
            ("Other Student", "student2@t.io", "student"),
        ]:
            user = User(name=name, email=email, role=role)
            user.set_password("Passw0rd!")
            db.session.add(user)
        db.session.commit()
        db.session.remove()
    # Do not keep an app context open during the test: Flask would reuse it for
    # every request and Flask-Login's cached user would leak between clients.
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def make_client(app):
    def _make(email):
        client = app.test_client()
        res = client.post("/api/auth/login", json={"email": email, "password": "Passw0rd!"})
        assert res.status_code == 200, res.get_json()
        return client

    return _make


@pytest.fixture()
def ticket(app, make_client):
    """A complaint raised by the demo student; returns its id."""
    client = make_client("student@t.io")
    res = client.post(
        "/api/complaints",
        json={
            "title": "Broken tube light",
            "description": "The tube light in room 204 flickers constantly.",
            "category_id": 1,
            "location": "Hostel B, room 204",
            "priority": "High",
        },
    )
    assert res.status_code == 201, res.get_json()
    return res.get_json()["id"]
