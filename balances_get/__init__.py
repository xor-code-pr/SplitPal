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
    group_id_raw = route_group_id or req.params.get('group_id') or ((body or {}) .get('group_id'))
    if not group_id_raw:
        return func.HttpResponse("Missing group_id", status_code=400)
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        try:
            group_id = int(group_id_raw)
        except (TypeError, ValueError):
            return func.HttpResponse("Invalid group_id", status_code=400)

        if not user_in_group(db, user.id, group_id):
            return func.HttpResponse("Not a member", status_code=403)
        txns = db.query(Transaction).filter(Transaction.group_id == group_id).all()
        # fetch members to ensure balances include zero rows
        members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
        member_ids = {m.user_id for m in members}

        cent = decimal.Decimal('0.01')
        balances = {uid: decimal.Decimal('0.00') for uid in member_ids}

        for txn in txns:
            payer = txn.payer_user_id
            if payer is None:
                continue
            amt = decimal.Decimal(str(txn.amount)).quantize(cent)
            balances.setdefault(payer, decimal.Decimal('0.00'))
            balances[payer] += amt

        splits = (
            db.query(Split)
            .join(Transaction, Split.transaction_id == Transaction.id)
            .filter(Transaction.group_id == group_id)
            .all()
        )
        for s in splits:
            share = decimal.Decimal(str(s.share_amount)).quantize(cent)
            balances.setdefault(s.user_id, decimal.Decimal('0.00'))
            balances[s.user_id] -= share

        total_balance = sum(balances.values())
        if total_balance != decimal.Decimal('0.00') and abs(total_balance) <= cent and balances:
            first_key = next(iter(balances))
            balances[first_key] = (balances[first_key] - total_balance).quantize(cent)

        user_ids = list(balances.keys())
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u.name for u in users}
        balances_out = [
            {
                "user_id": uid,
                "user_name": user_map.get(uid),
                "balance": str(amount.quantize(cent))
            }
            for uid, amount in balances.items()
        ]
        return func.HttpResponse(json.dumps({"balances": balances_out}), status_code=200, mimetype="application/json")
    finally:
        db.close()
