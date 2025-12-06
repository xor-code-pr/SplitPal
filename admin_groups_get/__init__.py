import json, azure.functions as func

from auth_decorator import require_auth, user_is_admin
from db_sqlite import SessionLocal
from logging_utils import ensure_request_logger
from models import Group

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    log = ensure_request_logger(req, name=__name__, user=user)
    db = SessionLocal()
    try:
        if not user_is_admin(db, user.id, None):
            log.warning("Non-admin attempted to list all groups")
            return func.HttpResponse("Admin privileges required", status_code=403)
        groups = db.query(Group).order_by(Group.id.asc()).all()
        out = [{"id": g.id, "name": g.name, "created_by": g.created_by} for g in groups]
        log.info("Listed all groups", extra={"group_count": len(out)})
        return func.HttpResponse(json.dumps({"groups": out}), status_code=200, mimetype="application/json")
    finally:
        db.close()
