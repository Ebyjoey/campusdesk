def staff_id(admin, email="Staff"):
    users = admin.get("/api/users?role=staff").get_json()
    return next(u["id"] for u in users if u["name"] == email)


def set_status(client, ticket, status):
    return client.patch(f"/api/complaints/{ticket}/status", json={"status": status})


def test_full_lifecycle_and_history(make_client, ticket):
    admin = make_client("admin@t.io")
    staff = make_client("staff@t.io")
    student = make_client("student@t.io")

    res = admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": staff_id(admin)})
    assert res.status_code == 200 and res.get_json()["status"] == "Assigned"
    assert set_status(staff, ticket, "In Progress").status_code == 200
    res = set_status(staff, ticket, "Resolved")
    assert res.status_code == 200 and res.get_json()["resolved_at"]
    assert set_status(student, ticket, "Closed").status_code == 200

    data = student.get(f"/api/complaints/{ticket}").get_json()
    assert [h["new_status"] for h in data["history"]] == [
        "Open", "Assigned", "In Progress", "Resolved", "Closed",
    ]
    assert data["history"][-1]["changed_by"] == "Student"


def test_invalid_transitions_rejected(make_client, ticket):
    admin = make_client("admin@t.io")
    assert set_status(admin, ticket, "Resolved").status_code == 409
    assert set_status(admin, ticket, "Closed").status_code == 409
    assert set_status(admin, ticket, "Nonsense").status_code == 400


def test_wrong_person_cannot_change_status(make_client, ticket):
    admin = make_client("admin@t.io")
    admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": staff_id(admin)})
    student = make_client("student@t.io")
    assert set_status(student, ticket, "In Progress").status_code == 403
    # a different staff member cannot even see the ticket
    assert set_status(make_client("staff2@t.io"), ticket, "In Progress").status_code == 404


def test_student_can_reopen_resolved(make_client, ticket):
    admin = make_client("admin@t.io")
    staff = make_client("staff@t.io")
    student = make_client("student@t.io")
    admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": staff_id(admin)})
    set_status(staff, ticket, "In Progress")
    set_status(staff, ticket, "Resolved")
    res = set_status(student, ticket, "In Progress")
    assert res.status_code == 200
    assert res.get_json()["resolved_at"] is None
    assert set_status(staff, ticket, "Resolved").status_code == 200
    assert set_status(staff, ticket, "Closed").status_code == 403


def test_assign_rules(make_client, ticket):
    admin = make_client("admin@t.io")
    student = make_client("student@t.io")
    assert student.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": 1}).status_code == 403
    assert admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": 999}).status_code == 400
    student_user_id = student.get("/api/auth/me").get_json()["id"]
    assert admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": student_user_id}).status_code == 400
    assert admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": staff_id(admin)}).status_code == 200
    # reassign while still Assigned is allowed
    assert admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": staff_id(admin, "Other Staff")}).status_code == 200


def test_categories_admin_only_and_protected(make_client, ticket):
    admin = make_client("admin@t.io")
    student = make_client("student@t.io")
    assert student.post("/api/categories", json={"name": "Library"}).status_code == 403
    res = admin.post("/api/categories", json={"name": "Library", "default_department": "Lib"})
    assert res.status_code == 201
    assert admin.post("/api/categories", json={"name": "library"}).status_code == 409
    assert admin.delete(f"/api/categories/{res.get_json()['id']}").status_code == 200
    # category 1 is used by the ticket
    assert admin.delete("/api/categories/1").status_code == 409
    assert len(student.get("/api/categories").get_json()) == 2


def test_stats_summary(make_client, ticket):
    admin = make_client("admin@t.io")
    staff = make_client("staff@t.io")
    stats = admin.get("/api/stats/summary").get_json()
    assert stats["total"] == 1 and stats["by_status"]["Open"] == 1
    assert stats["avg_resolution_hours"] is None
    admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": staff_id(admin)})
    set_status(staff, ticket, "In Progress")
    set_status(staff, ticket, "Resolved")
    stats = admin.get("/api/stats/summary").get_json()
    assert stats["by_status"]["Resolved"] == 1
    assert stats["avg_resolution_hours"] is not None
    assert stats["by_category"] == {"Hostel": 1}
