def payload(**over):
    data = {
        "title": "Wi-Fi down in library",
        "description": "No connectivity on the second floor since morning.",
        "category_id": 2,
        "location": "Library 2F",
        "priority": "Medium",
    }
    data.update(over)
    return data


def test_create_validates_input(make_client):
    c = make_client("student@t.io")
    assert c.post("/api/complaints", json=payload(title="hi")).status_code == 400
    assert c.post("/api/complaints", json=payload(description="short")).status_code == 400
    assert c.post("/api/complaints", json=payload(priority="Urgent")).status_code == 400
    assert c.post("/api/complaints", json=payload(category_id=999)).status_code == 400
    assert c.post("/api/complaints", json=payload(category_id="2")).status_code == 400


def test_ticket_number_and_initial_history(make_client, ticket):
    c = make_client("student@t.io")
    data = c.get(f"/api/complaints/{ticket}").get_json()
    assert data["ticket_no"].startswith("CD-") and data["ticket_no"].endswith(f"{ticket:05d}")
    assert data["status"] == "Open"
    assert [h["new_status"] for h in data["history"]] == ["Open"]


def test_only_students_create(make_client):
    assert make_client("admin@t.io").post("/api/complaints", json=payload()).status_code == 403
    assert make_client("staff@t.io").post("/api/complaints", json=payload()).status_code == 403


def test_visibility_rules(make_client, ticket):
    assert make_client("student@t.io").get(f"/api/complaints/{ticket}").status_code == 200
    assert make_client("student2@t.io").get(f"/api/complaints/{ticket}").status_code == 404
    assert make_client("staff@t.io").get(f"/api/complaints/{ticket}").status_code == 404
    assert make_client("admin@t.io").get(f"/api/complaints/{ticket}").status_code == 200
    assert make_client("student2@t.io").get("/api/complaints").get_json() == []
    assert len(make_client("admin@t.io").get("/api/complaints").get_json()) == 1


def test_list_filters(make_client, ticket):
    admin = make_client("admin@t.io")
    assert len(admin.get("/api/complaints?priority=High").get_json()) == 1
    assert admin.get("/api/complaints?priority=Low").get_json() == []
    assert admin.get("/api/complaints?status=Resolved").get_json() == []
    assert len(admin.get("/api/complaints?category=1").get_json()) == 1


def test_edit_only_owner_while_open(make_client, ticket):
    s = make_client("student@t.io")
    assert s.put(f"/api/complaints/{ticket}", json={"title": "Updated title ok"}).status_code == 200
    assert s.put(f"/api/complaints/{ticket}", json={"title": "x"}).status_code == 400
    admin = make_client("admin@t.io")
    assert admin.put(f"/api/complaints/{ticket}", json={"title": "Admin edit"}).status_code == 403
    staff_id = admin.get("/api/users?role=staff").get_json()[0]["id"]
    admin.patch(f"/api/complaints/{ticket}/assign", json={"staff_id": staff_id})
    assert s.put(f"/api/complaints/{ticket}", json={"title": "Too late now"}).status_code == 409


def test_comments(make_client, ticket):
    s = make_client("student@t.io")
    assert s.post(f"/api/complaints/{ticket}/comments", json={"body": ""}).status_code == 400
    assert s.post(f"/api/complaints/{ticket}/comments", json={"body": "Any update?"}).status_code == 201
    assert make_client("admin@t.io").post(f"/api/complaints/{ticket}/comments", json={"body": "On it"}).status_code == 201
    assert make_client("student2@t.io").post(f"/api/complaints/{ticket}/comments", json={"body": "hi"}).status_code == 404
    assert len(s.get(f"/api/complaints/{ticket}/comments").get_json()) == 2


def test_admin_can_delete(make_client, ticket):
    assert make_client("student@t.io").delete(f"/api/complaints/{ticket}").status_code == 403
    assert make_client("admin@t.io").delete(f"/api/complaints/{ticket}").status_code == 200
    assert make_client("admin@t.io").get(f"/api/complaints/{ticket}").status_code == 404
