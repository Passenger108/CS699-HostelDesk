from app.common.errors import fail
from app.extensions import db
from app.hostel_structure.models import Floor, Hostel, Location, LocationKind, Room, Wing

HOSTEL_4 = {
    "code": "H4",
    "name": "Hostel 4",
    "floors": 9,
    "wings": "ABCDEFGH",
    "rooms_per_wing": 16,
    "facilities": ["Reception desk", "Common room", "Store room"],
}


def room_number(wing_code: str, floor_number: int, index: int) -> str:
    return f"{wing_code}{floor_number}{index:02d}"


def seed_hostel(code, name, floors, wings, rooms_per_wing, facilities) -> tuple[Hostel, bool]:
    existing = db.session.scalar(db.select(Hostel).filter_by(code=code))
    if existing:
        return existing, False

    hostel = Hostel(code=code, name=name)
    db.session.add(hostel)

    ground = Floor(number=0)
    hostel.floors.append(ground)
    for facility in facilities:
        db.session.add(
            Location(
                hostel=hostel,
                kind=LocationKind.GROUND_FACILITY,
                floor=ground,
                facility_name=facility,
            )
        )

    for number in range(1, floors + 1):
        floor = Floor(number=number)
        hostel.floors.append(floor)
        for wing_code in wings:
            wing = Wing(code=wing_code)
            floor.wings.append(wing)
            for index in range(1, rooms_per_wing + 1):
                wing.rooms.append(Room(number=room_number(wing_code, number, index)))
            db.session.add(
                Location(hostel=hostel, kind=LocationKind.FLOOR_WING, floor=floor, wing=wing)
            )

    db.session.flush()
    return hostel, True


def seed_hostel_4() -> tuple[Hostel, bool]:
    return seed_hostel(**HOSTEL_4)


def get_hostel(code: str = HOSTEL_4["code"]) -> Hostel:
    hostel = db.session.scalar(db.select(Hostel).filter_by(code=code))
    if hostel is None:
        raise fail("HOSTEL_NOT_FOUND")
    return hostel


def find_room(number: str) -> Room | None:
    return db.session.scalar(db.select(Room).filter_by(number=number))


def room_dict(room: Room | None) -> dict | None:
    if room is None:
        return None
    floor = room.wing.floor
    return {
        "id": room.id,
        "number": room.number,
        "floor": floor.number,
        "floor_label": floor.label,
        "wing": room.wing.code,
    }


def location_dict(location: Location | None) -> dict | None:
    if location is None:
        return None
    return {
        "id": location.id,
        "kind": location.kind.value,
        "floor": location.floor.number,
        "wing": location.wing.code if location.wing else None,
        "facility_name": location.facility_name,
        "label": location.label,
    }


def structure_dict(hostel: Hostel) -> dict:
    facilities = db.session.scalars(
        db.select(Location)
        .filter_by(hostel_id=hostel.id, kind=LocationKind.GROUND_FACILITY)
        .order_by(Location.id)
    ).all()
    return {
        "id": hostel.id,
        "code": hostel.code,
        "name": hostel.name,
        "floors": [
            {
                "id": floor.id,
                "number": floor.number,
                "label": floor.label,
                "wings": [
                    {
                        "id": wing.id,
                        "code": wing.code,
                        "rooms": [{"id": room.id, "number": room.number} for room in wing.rooms],
                    }
                    for wing in floor.wings
                ],
                "facilities": [location_dict(f) for f in facilities if f.floor_id == floor.id],
            }
            for floor in hostel.floors
        ],
    }


def list_locations(hostel: Hostel) -> list[dict]:
    locations = db.session.scalars(
        db.select(Location)
        .join(Floor, Location.floor_id == Floor.id)
        .outerjoin(Wing, Location.wing_id == Wing.id)
        .filter(Location.hostel_id == hostel.id)
        .order_by(Floor.number, Wing.code, Location.facility_name)
    ).all()
    return [location_dict(location) for location in locations]
