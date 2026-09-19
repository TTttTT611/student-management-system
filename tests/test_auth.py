def test_login_success(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    assert res.json()["token_type"] == "bearer"


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert res.status_code == 401


def test_me(client, admin):
    res = client.get("/api/auth/me", headers=admin)
    assert res.status_code == 200
    assert res.json() == {"id": 1, "username": "admin", "role": "admin"}


def test_requires_auth(client):
    assert client.get("/api/students").status_code == 401
    assert client.get("/api/students", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_viewer_cannot_write(client, viewer, student_payload):
    res = client.post("/api/students", json=student_payload, headers=viewer)
    assert res.status_code == 403


def test_admin_manages_users(client, admin, viewer):
    res = client.post("/api/auth/users", json={"username": "u2", "password": "secret1"}, headers=admin)
    assert res.status_code == 201
    uid = res.json()["id"]

    assert client.post("/api/auth/users", json={"username": "u2", "password": "secret1"}, headers=admin).status_code == 400
    assert client.get("/api/auth/users", headers=viewer).status_code == 403
    assert client.delete("/api/auth/users/1", headers=admin).status_code == 400  # cannot delete yourself
    assert client.delete(f"/api/auth/users/{uid}", headers=admin).status_code == 204


def test_password_too_long_rejected(client, admin):
    long_password = "\u5bc6" * 30  # 30 CJK characters = 90 bytes, over the bcrypt limit
    res = client.post("/api/auth/users", json={"username": "u3", "password": long_password}, headers=admin)
    assert res.status_code == 422

    # an over-long password on login must not cause a 500
    res = client.post("/api/auth/login", json={"username": "admin", "password": "a" * 100})
    assert res.status_code == 401


def test_cookie_session(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    assert "sms_session" in res.cookies
    # subsequent requests rely on the cookie only, no Authorization header
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers
    # other usernames from the same IP are locked too
    assert client.post("/api/auth/login", json={"username": "viewer", "password": "viewer123"}).status_code == 429


def test_change_password(client, admin):
    res = client.post("/api/auth/change-password", json={"old_password": "wrong", "new_password": "newpass1"}, headers=admin)
    assert res.status_code == 400
    res = client.post("/api/auth/change-password", json={"old_password": "admin123", "new_password": "admin123"}, headers=admin)
    assert res.status_code == 400
    res = client.post("/api/auth/change-password", json={"old_password": "admin123", "new_password": "newpass1"}, headers=admin)
    assert res.status_code == 204
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "newpass1"}).status_code == 200


def test_admin_reset_password(client, admin, viewer):
    assert client.put("/api/auth/users/2/password", json={"new_password": "reset123"}, headers=viewer).status_code == 403
    assert client.put("/api/auth/users/2/password", json={"new_password": "reset123"}, headers=admin).status_code == 204
    assert client.put("/api/auth/users/999/password", json={"new_password": "reset123"}, headers=admin).status_code == 404
    assert client.post("/api/auth/login", json={"username": "viewer", "password": "reset123"}).status_code == 200


def test_audit_log(client, admin, viewer, student_payload):
    client.post("/api/students", json=student_payload, headers=admin)
    client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    client.post("/api/auth/change-password", json={"old_password": "a", "new_password": "bbbbbb"}, headers=admin)

    assert client.get("/api/audit-logs", headers=viewer).status_code == 403
    res = client.get("/api/audit-logs", headers=admin)
    assert res.status_code == 200
    logs = res.json()["items"]
    paths = [(l["path"], l["status"], l["username"]) for l in logs]
    assert ("/api/students", 201, "admin") in paths
    assert ("/api/auth/login", 401, "ghost") in paths

    pw_log = next(l for l in logs if l["path"] == "/api/auth/change-password")
    assert "***" in pw_log["detail"] and "bbbbbb" not in pw_log["detail"]
    student_log = next(l for l in logs if l["path"] == "/api/students")
    assert "Alice Smith" in student_log["detail"]

    res = client.get("/api/audit-logs", params={"username": "ghost"}, headers=admin).json()
    assert res["total"] == 1
