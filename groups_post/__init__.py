import json
import azure.functions as func
from db_sqlite import SessionLocal
from models import Group, GroupMember
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
    name = data.get("name")
    if not name:
        return apply_cors(func.HttpResponse("Missing name", status_code=400))
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        g = Group(name=name, created_by=user.id)
        db.add(g)
        db.commit()
        db.refresh(g)
        gm = GroupMember(group_id=g.id, user_id=user.id, role='admin')
        db.add(gm)
        db.commit()
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
