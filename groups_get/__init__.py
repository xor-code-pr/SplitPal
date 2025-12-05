import json, azure.functions as func
from db_sqlite import SessionLocal
from models import Group, GroupMember, User
from auth_decorator import require_auth

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
                db.query(GroupMember.group_id, User.id, User.name)
                .join(User, GroupMember.user_id == User.id)
                .filter(GroupMember.group_id.in_(group_ids))
                .all()
            )
            for group_id, member_id, member_name in member_rows:
                members_map.setdefault(group_id, []).append({
                    "user_id": member_id,
                    "user_name": member_name
                })

        groups = [{
            "group_id": g.id,
            "group_name": g.name,
            "created_by_id": g.created_by,
            "created_by_name": name_map.get(g.created_by),
            "members": members_map.get(g.id, [])
        } for g in rows]
        return func.HttpResponse(json.dumps({"groups": groups}), status_code=200, mimetype="application/json")
    finally:
        db.close()
