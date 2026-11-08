def login(client, email):
    return client.post("/login", data={"email": email, "password": "Passw0rd!"})


def test_register_page_creates_account(app):
    client = app.test_client()
    res = client.post(
        "/register", data={"name": "Page User", "email": "page@t.io", "password": "longenough1"}
    )
    assert res.status_code == 302
    res = client.post("/login", data={"email": "page@t.io", "password": "longenough1"})
    assert res.status_code == 302


def test_bad_html_login_shows_error(app):
    res = login(app.test_client(), "student@t.io".replace("student", "nobody"))
    assert res.status_code == 200 and b"Invalid email or password" in res.data


def test_student_raises_complaint_via_form(app):
    client = app.test_client()
    login(client, "student@t.io")
    res = client.post(
        "/complaints/new",
        data={
            "title": "Leaking tap in mess",
            "category_id": 1,
            "location": "Mess hall",
            "priority": "High",
            "description": "The tap near the entrance leaks all day.",
        },
    )
    assert res.status_code == 302 and "/complaints/1" in res.headers["Location"]
    assert b"Leaking tap in mess" in client.get("/complaints").data


def test_admin_adds_and_removes_category_via_form(app):
    client = app.test_client()
    login(client, "admin@t.io")
    res = client.post("/admin/categories", data={"name": "Library", "default_department": "Lib"})
    assert res.status_code == 302
    assert b"Remove Library" in client.get("/admin/categories").data
    assert client.post("/admin/categories/3/delete").status_code == 302
    assert b"Remove Library" not in client.get("/admin/categories").data


def test_logout_and_404_page(app):
    client = app.test_client()
    login(client, "student@t.io")
    assert client.post("/logout").status_code == 302
    assert client.get("/dashboard").status_code == 302
    assert client.get("/no-such-page").status_code == 404


def test_seeded_demo_accounts_can_sign_in_through_the_form(app):
    """Regression: the form's email validator rejects reserved domains like .local."""
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed", "--password", "DemoPass123!"])
    assert result.exit_code == 0
    for email in ("admin@campusdesk.in", "staff1@campusdesk.in", "student@campusdesk.in"):
        client = app.test_client()
        res = client.post("/login", data={"email": email, "password": "DemoPass123!"})
        assert res.status_code == 302, email
