from datetime import datetime

from app.cleaning.models import CleaningRequest, OfferStatus
from app.workers.service import list_workers

NEARBY_FLOORS = 2
SOON_MINUTES = 10
REFUSED = (OfferStatus.DECLINED, OfferStatus.TIMED_OUT)
REASONS = {
    1: "Available on the same floor ({place}).",
    2: "Busy on the same floor ({place}), free in about {minutes} min.",
    3: "Available, {floors} away ({place}).",
    4: "Available, {floors} away ({place}).",
    5: "Busy, {floors} away ({place}), free in about {minutes} min.",
}


def tier(availability: str, distance: int | None, minutes: int) -> int | None:
    near = distance is not None and distance <= NEARBY_FLOORS
    if availability == "AVAILABLE":
        return 1 if distance == 0 else 3 if near else 4
    if availability == "BUSY" and distance == 0 and minutes <= SOON_MINUTES:
        return 2
    return 5 if availability == "BUSY" and near else None


def _reason(rank: int, worker: dict, distance: int | None) -> str:
    if distance is None:
        return "Available, location not known."
    return REASONS[rank].format(
        place=worker["last_location"]["label"],
        minutes=worker["busy_minutes"],
        floors=f"{distance} floor{'' if distance == 1 else 's'}",
    )


def _warnings(worker: dict) -> list[str]:
    warnings = []
    if worker["freshness"] == "STALE":
        warnings.append(
            f"Location is {worker['location_age_minutes']} min old. Call to confirm where they are."
        )
    if worker["freshness"] == "UNKNOWN":
        warnings.append("No location shared yet. Call to confirm where they are.")
    if worker["tasks"]:
        warnings.append(
            f"Already has {len(worker['tasks'])} accepted task(s), "
            f"about {worker['busy_minutes']} min of work left."
        )
    return warnings


def recommend(request: CleaningRequest, now: datetime | None = None) -> list[dict]:
    floor = request.room_snapshot["floor"]
    ranked = []
    refused = {offer.worker_id for offer in request.offers if offer.status in REFUSED}
    for worker in list_workers(now):
        location = worker["last_location"]
        distance = abs(location["floor"] - floor) if location else None
        rank = tier(worker["availability"], distance, worker["busy_minutes"])
        if rank and worker["id"] not in refused:
            pick = {
                "worker": worker,
                "tier": rank,
                "reason": _reason(rank, worker, distance),
                "warnings": _warnings(worker),
            }
            order = (rank, 99 if distance is None else distance, worker["busy_minutes"])
            ranked.append((order, pick))
    return [pick for _, pick in sorted(ranked, key=lambda item: item[0])]
