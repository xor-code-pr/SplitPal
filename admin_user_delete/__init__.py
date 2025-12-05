import json
from decimal import Decimal
import azure.functions as func
from db_sqlite import SessionLocal
from models import User, GroupMember, Transaction, Split, TransactionHistory
from auth_decorator import require_auth
from auth_decorator import user_is_admin


def _compute_group_balance(db, group_id: int, member_id: int) -> Decimal:
    transactions = db.query(Transaction).filter(Transaction.group_id == group_id).all()
    if not transactions:
        return Decimal('0.00')

    payer_map = {txn.id: txn.payer_user_id for txn in transactions}
    splits = (
        db.query(Split)
        .join(Transaction, Split.transaction_id == Transaction.id)
        .filter(Transaction.group_id == group_id)
        .all()
    )

    balance = Decimal('0.00')
    for split in splits:
        payer_id = payer_map.get(split.transaction_id)
        if payer_id is None:
            continue

        amount = Decimal(str(split.share_amount))
        if split.user_id == member_id and payer_id != member_id:
            balance -= amount
        elif payer_id == member_id and split.user_id != member_id:
            balance += amount

    return balance

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    user_id = req.route_params.get('id') or req.params.get('id')
    if not user_id:
        return func.HttpResponse("Missing user id", status_code=400)
    db = SessionLocal()
    try:
        if not user_is_admin(db, user.id, None):
            return func.HttpResponse("Admin privileges required", status_code=403)
        target = db.query(User).filter(User.id == int(user_id)).first()
        if not target:
            return func.HttpResponse("User not found", status_code=404)
        # Remove memberships

        memberships = db.query(GroupMember).filter(GroupMember.user_id == int(user_id)).all()
        pending_balances = []
        for membership in memberships:
            balance = _compute_group_balance(db, membership.group_id, int(user_id))
            if abs(balance) > Decimal('0.009'):
                pending_balances.append(
                    {
                        "group_id": membership.group_id,
                        "balance": str(balance.quantize(Decimal('0.01')))
                    }
                )

        if pending_balances:
            payload = {
                "error": "Cannot delete user with unsettled balances",
                "pending": pending_balances
            }
            return func.HttpResponse(json.dumps(payload), status_code=400, mimetype="application/json")
        db.query(GroupMember).filter(GroupMember.user_id == int(user_id)).delete()
        # Clean up transactions where the user was the payer
        payer_transactions = db.query(Transaction).filter(Transaction.payer_user_id == int(user_id)).all()
        for tx in payer_transactions:
            db.query(Split).filter(Split.transaction_id == tx.id).delete()
            db.query(TransactionHistory).filter(TransactionHistory.transaction_id == tx.id).delete()
            db.delete(tx)
        # Remove splits where the user participated in others' transactions
        db.query(Split).filter(Split.user_id == int(user_id)).delete()
        # Remove history entries authored by this user
        db.query(TransactionHistory).filter(TransactionHistory.actor_user_id == int(user_id)).delete()
        # Delete user
        db.delete(target)
        db.commit()
        return func.HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json")
    finally:
        db.close()
