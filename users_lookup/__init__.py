import json
import azure.functions as func
from sqlalchemy import func as sa_func
from db_sqlite import SessionLocal
from models import User
from auth_decorator import require_auth
from http_utils import apply_cors, preflight_response


@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()

    query = (req.params.get("q") or "").strip()
    limit_param = req.params.get("limit") or "10"

    try:
        limit = max(1, min(int(limit_param), 25))
    except ValueError:
        limit = 10

    db = SessionLocal()
    try:
        stmt = db.query(User)
        if query:
            lowered = f"%{query.lower()}%"
            stmt = stmt.filter(sa_func.lower(User.email).like(lowered))
        users = (
            stmt.order_by(User.email.asc())
            .limit(limit)
            .all()
        )
        data = [{"id": u.id, "name": u.name, "email": u.email} for u in users]
        return apply_cors(
            func.HttpResponse(
                json.dumps({"users": data}),
                status_code=200,
                mimetype="application/json"
            )
        )
    finally:
        db.close()
