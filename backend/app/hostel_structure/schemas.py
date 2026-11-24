from app.extensions import db
from app.hostel_structure.models import Hostel, Location, LocationKind, Room


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
