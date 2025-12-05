import json
from decimal import Decimal
import azure.functions as func
from db_sqlite import SessionLocal
from models import Group, GroupMember
from auth_decorator import require_auth
from http_utils import apply_cors, preflight_response
from balance_utils import compute_member_balance


@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()

    route_params = getattr(req, "route_params", {})
    group_id_raw = route_params.get("group_id") or req.params.get("group_id")
    member_id_raw = route_params.get("member_id") or req.params.get("member_id")

    if not group_id_raw or not member_id_raw:
        return apply_cors(func.HttpResponse("Missing group_id or member_id", status_code=400))

    try:
        group_id = int(group_id_raw)
        member_id = int(member_id_raw)
    except ValueError:
        return apply_cors(func.HttpResponse("Invalid identifiers", status_code=400))

    user = getattr(req, "current_user")
    if user.id == member_id:
        return apply_cors(func.HttpResponse("You cannot remove yourself from the group", status_code=400))

    db = SessionLocal()
    try:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return apply_cors(func.HttpResponse("Group not found", status_code=404))

        if group.created_by != user.id:
            return apply_cors(func.HttpResponse("Only the group creator can remove members", status_code=403))

        membership = (
            db.query(GroupMember)
            .filter(GroupMember.group_id == group_id, GroupMember.user_id == member_id)
            .first()
        )
        if not membership:
            return apply_cors(func.HttpResponse("User is not a member of this group", status_code=404))

        if membership.user_id == group.created_by:
            return apply_cors(func.HttpResponse("Group creator cannot be removed", status_code=400))

        balance = compute_member_balance(db, group_id, member_id)
        if abs(balance) > Decimal('0.009'):
            return apply_cors(func.HttpResponse("Cannot remove member with unsettled balance", status_code=400))

        db.delete(membership)
        db.commit()

        payload = {"ok": True, "removed_user_id": member_id}
        return apply_cors(func.HttpResponse(json.dumps(payload), status_code=200, mimetype="application/json"))
    finally:
        db.close()
