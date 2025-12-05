import json, azure.functions as func
from db_sqlite import SessionLocal
from models import User
from auth_decorator import require_auth
from auth_decorator import user_is_admin

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        if not user_is_admin(db, user.id, None):
            return func.HttpResponse("Admin privileges required", status_code=403)
        users = db.query(User).order_by(User.id.asc()).all()
        out = [{"id": u.id, "name": u.name, "email": u.email, "created_at": getattr(u, 'created_at', None).isoformat() if getattr(u, 'created_at', None) else None} for u in users]
        return func.HttpResponse(json.dumps({"users": out}), status_code=200, mimetype="application/json")
    finally:
        db.close()
