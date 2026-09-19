import pytest


@pytest.fixture
def setup(client, admin, student_payload):
    sid = client.post("/api/students", json=student_payload, headers=admin).json()["id"]
    cid = client.post("/api/courses", json={"code": "CS101", "name": "Programming 101", "credit": 3}, headers=admin).json()["id"]
    return sid, cid


def test_course_crud(client, admin):
    res = client.post("/api/courses", json={"code": "CS101", "name": "Programming 101", "credit": 3}, headers=admin)
    assert res.status_code == 201
    cid = res.json()["id"]
    assert client.post("/api/courses", json={"code": "CS101", "name": "x", "credit": 1}, headers=admin).status_code == 400
    assert client.put(f"/api/courses/{cid}", json={"credit": 4}, headers=admin).json()["credit"] == 4
    assert len(client.get("/api/courses", headers=admin).json()) == 1
    assert client.delete(f"/api/courses/{cid}", headers=admin).status_code == 204
    assert client.get(f"/api/courses/{cid}", headers=admin).status_code == 404


def test_enroll_and_grade(client, admin, setup):
    sid, cid = setup
    res = client.post("/api/enrollments", json={"student_id": sid, "course_id": cid}, headers=admin)
    assert res.status_code == 201, res.text
    eid = res.json()["id"]
    assert res.json()["score"] is None and res.json()["course_name"] == "Programming 101"

    assert client.post("/api/enrollments", json={"student_id": sid, "course_id": cid}, headers=admin).status_code == 400
    assert client.post("/api/enrollments", json={"student_id": 999, "course_id": cid}, headers=admin).status_code == 400

    res = client.put(f"/api/enrollments/{eid}", json={"score": 88.5}, headers=admin)
    assert res.status_code == 200 and res.json()["score"] == 88.5
    assert client.put(f"/api/enrollments/{eid}", json={"score": 101}, headers=admin).status_code == 422

    res = client.get("/api/enrollments", params={"student_id": sid}, headers=admin).json()
    assert len(res) == 1 and res[0]["student_name"] == "Alice Smith"

    assert client.delete(f"/api/enrollments/{eid}", headers=admin).status_code == 204
    assert client.get("/api/enrollments", headers=admin).json() == []


def test_deleting_student_removes_enrollments(client, admin, setup):
    sid, cid = setup
    client.post("/api/enrollments", json={"student_id": sid, "course_id": cid}, headers=admin)
    client.delete(f"/api/students/{sid}", headers=admin)
    assert client.get("/api/enrollments", headers=admin).json() == []


def test_stats(client, admin, student_payload):
    cid = client.post("/api/classes", json={"name": "Class 1"}, headers=admin).json()["id"]
    client.post("/api/students", json={**student_payload, "class_id": cid}, headers=admin)
    client.post("/api/students", json={**student_payload, "student_no": "S002", "gender": "male", "major": "Mathematics"}, headers=admin)
    client.post("/api/students", json={**student_payload, "student_no": "S003", "major": None}, headers=admin)

    res = client.get("/api/stats", headers=admin)
    assert res.status_code == 200
    body = res.json()
    assert body["total_students"] == 3 and body["total_classes"] == 1
    assert {i["label"]: i["count"] for i in body["by_gender"]} == {"female": 2, "male": 1}
    assert {i["label"]: i["count"] for i in body["by_major"]} == {"Computer Science": 1, "Mathematics": 1, "Unspecified": 1}
    assert {i["label"]: i["count"] for i in body["by_class"]} == {"Class 1": 1, "Unassigned": 2}
