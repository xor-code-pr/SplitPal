import json, azure.functions as func

from auth_decorator import require_auth, user_is_admin
from db_sqlite import SessionLocal
from logging_utils import ensure_request_logger
from models import User

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    log = ensure_request_logger(req, name=__name__, user=user)
    db = SessionLocal()
    try:
        if not user_is_admin(db, user.id, None):
            log.warning("Non-admin attempted to list users")
            return func.HttpResponse("Admin privileges required", status_code=403)
        users = db.query(User).order_by(User.id.asc()).all()
        out = [{"id": u.id, "name": u.name, "email": u.email, "created_at": getattr(u, 'created_at', None).isoformat() if getattr(u, 'created_at', None) else None} for u in users]
        log.info("Listed users", extra={"user_count": len(out)})
        return func.HttpResponse(json.dumps({"users": out}), status_code=200, mimetype="application/json")
    finally:
        db.close()
