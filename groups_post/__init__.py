import json

import azure.functions as func

from auth_decorator import require_auth
from db_sqlite import SessionLocal
from http_utils import apply_cors, preflight_response
from logging_utils import ensure_request_logger
from models import Group, GroupMember

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()

    try:
        data = req.get_json()
    except Exception:
        ensure_request_logger(req, name=__name__, user=getattr(req, "current_user", None))
        return apply_cors(func.HttpResponse("Invalid JSON", status_code=400))
    name = data.get("name")
    if not name:
        ensure_request_logger(req, name=__name__, user=getattr(req, "current_user", None))
        return apply_cors(func.HttpResponse("Missing name", status_code=400))
    user = getattr(req, "current_user")
    log = ensure_request_logger(req, name=__name__, user=user, extra={"group_name": name})
    db = SessionLocal()
    try:
        g = Group(name=name, created_by=user.id)
        db.add(g)
        db.commit()
        db.refresh(g)
        gm = GroupMember(group_id=g.id, user_id=user.id, role='admin')
        db.add(gm)
        db.commit()
        log.info("Created new group", extra={"group_id": g.id})
        payload = {
            "group": {
                "id": g.id,
                "name": g.name,
                "created_by_id": g.created_by
            }
        }
        return apply_cors(func.HttpResponse(json.dumps(payload), status_code=201, mimetype="application/json"))
    finally:
        db.close()
