import json, azure.functions as func
from db_sqlite import SessionLocal
from models import Transaction, Split, User, Group
from auth_decorator import require_auth, user_in_group

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = None
    route_group_id = getattr(req, 'route_params', {}).get('group_id')
    group_id = route_group_id or req.params.get('group_id') or ((body or {}) .get('group_id'))
    if not group_id:
        return func.HttpResponse("Missing group_id", status_code=400)
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        if not user_in_group(db, user.id, int(group_id)):
            return func.HttpResponse("Not a member of this group", status_code=403)
        txns = db.query(Transaction).filter(Transaction.group_id == int(group_id)).order_by(Transaction.created_at.desc()).all()
        # Preload user names
        user_ids = {t.payer_user_id for t in txns}
        user_ids.update({t.created_by for t in txns if getattr(t, 'created_by', None) is not None})
        for t in txns:
            split_ids = [s.user_id for s in db.query(Split.user_id).filter(Split.transaction_id == t.id).all()]
            user_ids.update(split_ids)
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u.name for u in users}
        group = db.query(Group).filter(Group.id == int(group_id)).first()
        out = []
        for t in txns:
            splits = db.query(Split).filter(Split.transaction_id == t.id).all()
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
                "splits": [{"split_id": s.id, "user_name": user_map.get(s.user_id), "share_amount": str(s.share_amount)} for s in splits]
            })
        return func.HttpResponse(json.dumps({"transactions": out}), status_code=200, mimetype="application/json")
    finally:
        db.close()
