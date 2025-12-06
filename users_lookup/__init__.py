import json

import azure.functions as func
from sqlalchemy import func as sa_func, or_

from auth_decorator import require_auth
from db_sqlite import SessionLocal
from http_utils import apply_cors, preflight_response
from logging_utils import ensure_request_logger
from models import User


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
    log = ensure_request_logger(
        req,
        name=__name__,
        user=getattr(req, "current_user", None),
        extra={"query": query, "limit_param": limit_param, "limit": limit},
    )

    db = SessionLocal()
    try:
        stmt = db.query(User)
        if query:
            lowered = f"%{query.lower()}%"
            stmt = stmt.filter(
                or_(
                    sa_func.lower(User.email).like(lowered),
                    sa_func.lower(User.name).like(lowered)
                )
            )
        users = (
            stmt.order_by(User.email.asc())
            .limit(limit)
            .all()
        )
        data = [{"id": u.id, "name": u.name, "email": u.email} for u in users]
        log.info("Performed user lookup", extra={"matched": len(data)})
        return apply_cors(
            func.HttpResponse(
                json.dumps({"users": data}),
                status_code=200,
                mimetype="application/json"
            )
        )
    finally:
        db.close()
