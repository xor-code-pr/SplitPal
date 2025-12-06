import json

import azure.functions as func

from auth_decorator import require_auth, user_in_group
from balance_utils import CENT, compute_group_balances
from db_sqlite import SessionLocal
from http_utils import apply_cors
from logging_utils import ensure_request_logger
from models import User

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = None
    # Prefer route param, then query string, then JSON body
    route_group_id = getattr(req, 'route_params', {}).get('group_id')
    group_id_raw = route_group_id or req.params.get('group_id') or ((body or {}) .get('group_id'))
    if not group_id_raw:
        ensure_request_logger(req, name=__name__, user=getattr(req, "current_user", None))
        return apply_cors(func.HttpResponse("Missing group_id", status_code=400))
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        try:
            group_id = int(group_id_raw)
        except (TypeError, ValueError):
            ensure_request_logger(req, name=__name__, user=user)
            return apply_cors(func.HttpResponse("Invalid group_id", status_code=400))

        log = ensure_request_logger(req, name=__name__, user=user, extra={"group_id": group_id})
        if not user_in_group(db, user.id, group_id):
            log.warning("User not part of group when requesting balances")
            return apply_cors(func.HttpResponse("Not a member", status_code=403))

        balances = compute_group_balances(db, group_id)
        user_ids = list(balances.keys())
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u.name for u in users}
        balances_out = [
            {
                "user_id": uid,
                "user_name": user_map.get(uid),
                "balance": str(amount.quantize(CENT))
            }
            for uid, amount in balances.items()
        ]
        log.info("Calculated group balances", extra={"member_count": len(balances_out)})
        return apply_cors(func.HttpResponse(json.dumps({"balances": balances_out}), status_code=200, mimetype="application/json"))
    finally:
        db.close()
