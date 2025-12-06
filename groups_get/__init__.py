import json, azure.functions as func
from db_sqlite import SessionLocal
from models import Group, GroupMember, User
from auth_decorator import require_auth
from http_utils import apply_cors

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        rows = db.query(Group).join(GroupMember, Group.id == GroupMember.group_id).filter(GroupMember.user_id == user.id).all()
        group_ids = [g.id for g in rows]
        creator_ids = {g.created_by for g in rows if g.created_by is not None}
        creators = db.query(User).filter(User.id.in_(creator_ids)).all() if creator_ids else []
        name_map = {u.id: u.name for u in creators}
        members_map = {}
        if group_ids:
            member_rows = (
                db.query(
                    GroupMember.group_id,
                    GroupMember.user_id,
                    GroupMember.role,
                    GroupMember.joined_at,
                    User.name,
                    User.global_admin
                )
                .join(User, GroupMember.user_id == User.id)
                .filter(GroupMember.group_id.in_(group_ids))
                .all()
            )
            for group_id, member_id, member_role, joined_at, member_name, is_global_admin in member_rows:
                normalized_role = (member_role or "").strip().lower()
                is_admin_flag = bool(
                    is_global_admin or normalized_role in ("admin", "owner")
                )
                members_map.setdefault(group_id, []).append({
                    "user_id": member_id,
                    "user_name": member_name,
                    "role": member_role,
                    "is_admin": is_admin_flag,
                    "joined_at": joined_at.isoformat() if joined_at else None
                })

        groups = [{
            "group_id": g.id,
            "group_name": g.name,
            "created_by_id": g.created_by,
            "created_by_name": name_map.get(g.created_by),
            "members": members_map.get(g.id, [])
        } for g in rows]
        return apply_cors(func.HttpResponse(json.dumps({"groups": groups}), status_code=200, mimetype="application/json"))
    finally:
        db.close()
