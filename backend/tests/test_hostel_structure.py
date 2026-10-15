from app.extensions import db
from app.hostel_structure.models import Room
from app.hostel_structure.service import seed_hostel


def test_structure_requires_login(client, hostel):
    assert client.get("/api/v1/hostel/structure").status_code == 401


def test_structure_lists_floors_wings_and_rooms(make_user, auth_get, hostel):
    make_user()
    res = auth_get("/api/v1/hostel/structure")
    assert res.status_code == 200
    body = res.get_json()["hostel"]
    assert body["name"] == "Hostel 4"
    assert [f["number"] for f in body["floors"]] == [0, 1, 2]

    ground, first = body["floors"][0], body["floors"][1]
    assert ground["label"] == "Ground floor"
    assert ground["wings"] == []
    assert [f["facility_name"] for f in ground["facilities"]] == ["Reception desk"]
    assert [w["code"] for w in first["wings"]] == ["A", "B"]
    assert [r["number"] for r in first["wings"][0]["rooms"]] == ["A101", "A102", "A103"]


def test_structure_missing_returns_404(make_user, auth_get):
    make_user()
    res = auth_get("/api/v1/hostel/structure")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "HOSTEL_NOT_FOUND"


def test_locations_cover_every_floor_wing_and_facility(make_user, auth_get, hostel):
    make_user()
    locations = auth_get("/api/v1/hostel/locations").get_json()["locations"]
    labels = [loc["label"] for loc in locations]
    assert labels == [
        "Ground floor, Reception desk",
        "Floor 1, Wing A",
        "Floor 1, Wing B",
        "Floor 2, Wing A",
        "Floor 2, Wing B",
    ]
    assert locations[0]["kind"] == "GROUND_FACILITY"
    assert locations[1]["kind"] == "FLOOR_WING"


def test_seeding_twice_creates_nothing_new(hostel):
    rooms_before = db.session.scalar(db.select(db.func.count(Room.id)))
    again, created = seed_hostel(
        code="H4",
        name="Hostel 4",
        floors=2,
        wings="AB",
        rooms_per_wing=3,
        facilities=["Reception desk"],
    )
    assert created is False
    assert again.id == hostel.id
    assert db.session.scalar(db.select(db.func.count(Room.id))) == rooms_before == 12
