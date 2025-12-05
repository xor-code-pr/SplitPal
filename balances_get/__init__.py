import decimal
import json
import azure.functions as func
from db_sqlite import SessionLocal
from models import GroupMember, Transaction, Split, User
from auth_decorator import require_auth, user_in_group

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = None
    # Prefer route param, then query string, then JSON body
    route_group_id = getattr(req, 'route_params', {}).get('group_id')
    group_id = route_group_id or req.params.get('group_id') or ((body or {}) .get('group_id'))
    if not group_id:
        return func.HttpResponse("Missing group_id", status_code=400)
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        if not user_in_group(db, user.id, int(group_id)):
            return func.HttpResponse("Not a member", status_code=403)
        txns = db.query(Transaction).filter(Transaction.group_id == int(group_id)).all()
        txn_payer = {t.id: t.payer_user_id for t in txns}
        # fetch members to ensure balances include zero rows
        members = db.query(GroupMember).filter(GroupMember.group_id == int(group_id)).all()
        member_ids = {m.user_id for m in members}

        splits = db.query(Split).join(Transaction, Split.transaction_id == Transaction.id).filter(Transaction.group_id == int(group_id)).all()
        balances = {uid: decimal.Decimal('0.00') for uid in member_ids}
        for s in splits:
            payer = txn_payer.get(s.transaction_id)
            if payer is None:
                continue
            uid = s.user_id
            amt = decimal.Decimal(str(s.share_amount))
            if uid == payer:
                continue
            balances.setdefault(payer, decimal.Decimal('0.00'))
            balances.setdefault(uid, decimal.Decimal('0.00'))
            balances[payer] += amt
            balances[uid] -= amt
        user_ids = list(balances.keys())
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u.name for u in users}
        balances_out = [
            {
                "user_id": uid,
                "user_name": user_map.get(uid),
                "balance": str(amount.quantize(decimal.Decimal('0.01')))
            }
            for uid, amount in balances.items()
        ]
        return func.HttpResponse(json.dumps({"balances": balances_out}), status_code=200, mimetype="application/json")
    finally:
        db.close()
