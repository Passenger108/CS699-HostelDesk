from flask import Blueprint, Response, jsonify, request

from app.auth.guards import roles_required
from app.cleaning.schemas import SUPERVISOR_ROLES
from app.reports.service import monthly_report, report_csv

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.get("/cleaning")
@roles_required(*SUPERVISOR_ROLES)
def cleaning_report():
    return jsonify(monthly_report(request.args.get("month")))


@bp.get("/cleaning.csv")
@roles_required(*SUPERVISOR_ROLES)
def cleaning_csv():
    text, name = report_csv(request.args.get("month"), request.args.get("table"))
    return Response(
        text,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
