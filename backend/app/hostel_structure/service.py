from app.common.errors import fail
from app.extensions import db
from app.hostel_structure.models import Floor, Hostel, Location, LocationKind, Room, Wing
from app.hostel_structure.schemas import location_dict

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


def find_location(floor_number: int, wing_code: str) -> Location | None:
    return db.session.scalar(
        db.select(Location)
        .join(Floor, Location.floor_id == Floor.id)
        .join(Wing, Location.wing_id == Wing.id)
        .filter(Floor.number == floor_number, Wing.code == wing_code)
    )


def list_locations(hostel: Hostel) -> list[dict]:
    locations = db.session.scalars(
        db.select(Location)
        .join(Floor, Location.floor_id == Floor.id)
        .outerjoin(Wing, Location.wing_id == Wing.id)
        .filter(Location.hostel_id == hostel.id)
        .order_by(Floor.number, Wing.code, Location.facility_name)
    ).all()
    return [location_dict(location) for location in locations]
