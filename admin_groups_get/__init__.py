import json, azure.functions as func
from db_sqlite import SessionLocal
from models import Group
from auth_decorator import require_auth
from auth_decorator import user_is_admin

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        if not user_is_admin(db, user.id, None):
            return func.HttpResponse("Admin privileges required", status_code=403)
        groups = db.query(Group).order_by(Group.id.asc()).all()
        out = [{"id": g.id, "name": g.name, "created_by": g.created_by} for g in groups]
        return func.HttpResponse(json.dumps({"groups": out}), status_code=200, mimetype="application/json")
    finally:
        db.close()
