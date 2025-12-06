import json

import azure.functions as func
from sqlalchemy import func as sa_func

from auth_decorator import require_auth, user_is_admin
from db_sqlite import SessionLocal
from http_utils import apply_cors, preflight_response
from logging_utils import ensure_request_logger
from models import Group, GroupMember, User

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()

    try:
        data = req.get_json()
    except Exception:
        ensure_request_logger(req, name=__name__, user=getattr(req, "current_user", None))
        return apply_cors(func.HttpResponse("Invalid JSON", status_code=400))

    group_id = data.get("group_id")
    if not group_id:
        ensure_request_logger(req, name=__name__, user=getattr(req, "current_user", None))
        return apply_cors(func.HttpResponse("Missing group_id", status_code=400))

    member_email_raw = data.get("member_email") or data.get("email")
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        try:
            group_id_int = int(group_id)
        except (TypeError, ValueError):
            ensure_request_logger(req, name=__name__, user=user)
            return apply_cors(func.HttpResponse("Invalid group_id", status_code=400))

        g = db.query(Group).filter(Group.id == group_id_int).first()
        if not g:
            ensure_request_logger(req, name=__name__, user=user, extra={"group_id": group_id})
            return apply_cors(func.HttpResponse("Group not found", status_code=404))

        current_membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id_int,
            GroupMember.user_id == user.id
        ).first()
        if not current_membership:
            ensure_request_logger(req, name=__name__, user=user, extra={"group_id": group_id_int})
            return apply_cors(func.HttpResponse("Not a member of this group", status_code=403))

        if not member_email_raw:
            log = ensure_request_logger(req, name=__name__, user=user, extra={"group_id": group_id_int})
            log.warning("Missing member_email in payload")
            return apply_cors(func.HttpResponse("Provide the email of the member to add", status_code=400))

        log = ensure_request_logger(req, name=__name__, user=user, extra={"group_id": group_id_int})

        if not user_is_admin(db, user.id, group_id_int):
            log.warning("Non-admin attempted to add member")
            return apply_cors(func.HttpResponse("Only group admins can add members", status_code=403))

        member_email = member_email_raw.strip().lower()
        if not member_email:
            log.warning("Member email provided but empty")
            return apply_cors(func.HttpResponse("Provide a valid email address", status_code=400))

        target_user = (
            db.query(User)
            .filter(sa_func.lower(User.email) == member_email)
            .first()
        )
        if not target_user:
            log.warning("Target user email not found", extra={"member_email": member_email})
            return apply_cors(func.HttpResponse("User not found", status_code=404))

        existing = db.query(GroupMember).filter(
            GroupMember.group_id == group_id_int,
            GroupMember.user_id == target_user.id
        ).first()
        if existing:
            log.info("User already member", extra={"member_email": member_email, "target_user_id": target_user.id})
            return apply_cors(func.HttpResponse("User already a member", status_code=400))

        role = 'admin' if target_user.id == g.created_by else 'member'
        gm = GroupMember(group_id=group_id_int, user_id=target_user.id, role=role)
        db.add(gm)
        db.commit()
        log = ensure_request_logger(
            req,
            name=__name__,
            user=user,
            extra={"group_id": group_id_int, "target_user_id": target_user.id, "assigned_role": role},
        )
        log.info("Added member to group")
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
