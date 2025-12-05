import json, azure.functions as func
from db_sqlite import SessionLocal
from models import TransactionHistory, Transaction, User
from auth_decorator import require_auth, user_in_group
from http_utils import apply_cors

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = None
    route_tx_id = getattr(req, 'route_params', {}).get('id')
    tx_id = route_tx_id or req.params.get('id') or ((body or {}) .get('transaction_id'))
    if not tx_id:
        return apply_cors(func.HttpResponse("Missing transaction id", status_code=400))
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        trx = db.query(Transaction).filter(Transaction.id == int(tx_id)).first()
        if not trx:
            return apply_cors(func.HttpResponse("Transaction not found", status_code=404))
        if not user_in_group(db, user.id, trx.group_id):
            return apply_cors(func.HttpResponse("Not a member of this group", status_code=403))
        entries = db.query(TransactionHistory).filter(TransactionHistory.transaction_id == int(tx_id)).order_by(TransactionHistory.created_at.desc()).all()
        actor_ids = {e.actor_user_id for e in entries if e.actor_user_id is not None}
        actors = db.query(User).filter(User.id.in_(actor_ids)).all() if actor_ids else []
        name_map = {u.id: u.name for u in actors}
        out = [{"history_id": e.id, "action": e.action, "data": e.data, "actor_user_name": name_map.get(e.actor_user_id), "created_at": e.created_at.isoformat()} for e in entries]
        return apply_cors(func.HttpResponse(json.dumps({"history": out}), status_code=200, mimetype="application/json"))
    finally:
        db.close()
