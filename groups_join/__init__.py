import json
import azure.functions as func
from sqlalchemy import func as sa_func
from db_sqlite import SessionLocal
from models import Group, GroupMember, User
from auth_decorator import require_auth
from http_utils import apply_cors, preflight_response

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()

    try:
        data = req.get_json()
    except Exception:
        return apply_cors(func.HttpResponse("Invalid JSON", status_code=400))

    group_id = data.get("group_id")
    if not group_id:
        return apply_cors(func.HttpResponse("Missing group_id", status_code=400))

    member_email_raw = data.get("member_email") or data.get("email")
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        g = db.query(Group).filter(Group.id == group_id).first()
        if not g:
            return apply_cors(func.HttpResponse("Group not found", status_code=404))

        current_membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user.id
        ).first()
        if not current_membership:
            return apply_cors(func.HttpResponse("Not a member of this group", status_code=403))

        if not member_email_raw:
            return apply_cors(func.HttpResponse("Only the group creator can add members by email.", status_code=403))

        if g.created_by != user.id:
            return apply_cors(func.HttpResponse("Only the group creator can add members", status_code=403))

        member_email = member_email_raw.strip().lower()
        if not member_email:
            return apply_cors(func.HttpResponse("Provide a valid email address", status_code=400))

        target_user = (
            db.query(User)
            .filter(sa_func.lower(User.email) == member_email)
            .first()
        )
        if not target_user:
            return apply_cors(func.HttpResponse("User not found", status_code=404))

        existing = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user.id
        ).first()
        if existing:
            return apply_cors(func.HttpResponse("User already a member", status_code=400))

        role = 'admin' if target_user.id == g.created_by else 'member'
        gm = GroupMember(group_id=group_id, user_id=target_user.id, role=role)
        db.add(gm)
        db.commit()
        payload = {
            "ok": True,
            "member": {
                "id": target_user.id,
                "name": target_user.name,
                "email": target_user.email,
                "role": role
            }
        }
        return apply_cors(func.HttpResponse(json.dumps(payload), status_code=200, mimetype="application/json"))
    finally:
        db.close()
