import json
import azure.functions as func
from db_sqlite import SessionLocal
from models import User
from auth_decorator import require_auth, user_in_group
from http_utils import apply_cors
from balance_utils import compute_group_balances, CENT

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
        return apply_cors(func.HttpResponse("Missing group_id", status_code=400))
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        try:
            group_id = int(group_id_raw)
        except (TypeError, ValueError):
            return apply_cors(func.HttpResponse("Invalid group_id", status_code=400))

        if not user_in_group(db, user.id, group_id):
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
        return apply_cors(func.HttpResponse(json.dumps({"balances": balances_out}), status_code=200, mimetype="application/json"))
    finally:
        db.close()
