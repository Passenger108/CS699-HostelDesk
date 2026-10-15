from flask import Blueprint, jsonify

from app.auth.guards import login_required
from app.hostel_structure.service import get_hostel, list_locations, structure_dict

bp = Blueprint("hostel", __name__, url_prefix="/hostel")


@bp.get("/structure")
@login_required
def structure():
    return jsonify({"hostel": structure_dict(get_hostel())})


@bp.get("/locations")
@login_required
def locations():
    return jsonify({"locations": list_locations(get_hostel())})
