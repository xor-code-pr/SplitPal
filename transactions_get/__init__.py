import json, azure.functions as func
from db_sqlite import SessionLocal
from models import Transaction, Split, User, Group
from auth_decorator import require_auth, user_in_group
from http_utils import apply_cors

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = None
    route_group_id = getattr(req, 'route_params', {}).get('group_id')
    group_id = route_group_id or req.params.get('group_id') or ((body or {}) .get('group_id'))
    if not group_id:
        return apply_cors(func.HttpResponse("Missing group_id", status_code=400))
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        group_id_int = int(group_id)
        if not user_in_group(db, user.id, group_id_int):
            return apply_cors(func.HttpResponse("Not a member of this group", status_code=403))

        txns = (
            db.query(Transaction)
            .filter(Transaction.group_id == group_id_int)
            .order_by(Transaction.created_at.desc())
            .all()
        )

        txn_ids = [t.id for t in txns]
        splits_by_txn = {tid: [] for tid in txn_ids}
        if txn_ids:
            splits = (
                db.query(Split)
                .filter(Split.transaction_id.in_(txn_ids))
                .all()
            )
            for split in splits:
                splits_by_txn.setdefault(split.transaction_id, []).append(split)

        user_ids = {t.payer_user_id for t in txns if t.payer_user_id is not None}
        user_ids.update({t.created_by for t in txns if getattr(t, 'created_by', None) is not None})
        for split_list in splits_by_txn.values():
            for split in split_list:
                user_ids.add(split.user_id)

        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u.name for u in users}
        group = db.query(Group).filter(Group.id == group_id_int).first()

        out = []
        for t in txns:
            splits = splits_by_txn.get(t.id, [])
            out.append({
                "transaction_id": t.id,
                "title": t.title,
                "amount": str(t.amount),
                "currency": t.currency,
                "payer_user_name": user_map.get(t.payer_user_id),
                "note": t.note,
                "group_name": group.name if group else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "created_by_user_id": getattr(t, 'created_by', None),
                "created_by_user_name": user_map.get(getattr(t, 'created_by', None)),
                "splits": [
                    {
                        "split_id": s.id,
                        "user_name": user_map.get(s.user_id),
                        "share_amount": str(s.share_amount)
                    }
                    for s in splits
                ]
            })

        return apply_cors(func.HttpResponse(json.dumps({"transactions": out}), status_code=200, mimetype="application/json"))
    finally:
        db.close()
