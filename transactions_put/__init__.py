import json, decimal, logging, azure.functions as func
from db_sqlite import SessionLocal
from models import Transaction, Split, TransactionHistory, User, GroupMember
from auth_decorator import require_auth, user_in_group
from sqlalchemy.exc import SQLAlchemyError
from http_utils import apply_cors

logger = logging.getLogger(__name__)

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    tx_id = req.route_params.get('id') or req.params.get('id')
    if not tx_id:
        return apply_cors(func.HttpResponse("Missing transaction id", status_code=400))
    try:
        payload = req.get_json()
    except:
        return apply_cors(func.HttpResponse("Invalid JSON", status_code=400))

    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        trx = db.query(Transaction).filter(Transaction.id == int(tx_id)).first()
        if not trx:
            return apply_cors(func.HttpResponse("Transaction not found", status_code=404))
        if not user_in_group(db, user.id, trx.group_id):
            return apply_cors(func.HttpResponse("Not a member of this group", status_code=403))

        member_rows = (
            db.query(GroupMember.user_id, User.name)
            .join(User, GroupMember.user_id == User.id)
            .filter(GroupMember.group_id == trx.group_id)
            .all()
        )
        name_to_id = {name.strip().lower(): uid for uid, name in member_rows}
        group_member_ids = {uid for uid, _ in member_rows}

        old_splits = db.query(Split).filter(Split.transaction_id == trx.id).all()
        old_snapshot = {
            "transaction": {"id": trx.id, "title": trx.title, "amount": str(trx.amount), "payer": trx.payer_user_id},
            "splits": [{"user_id": s.user_id, "share": str(s.share_amount)} for s in old_splits]
        }

        title = payload.get("title", trx.title)
        cent = decimal.Decimal('0.01')
        tolerance = decimal.Decimal('0.01')
        amount = decimal.Decimal(str(payload.get("amount", trx.amount))).quantize(cent)
        payer_user_name = payload.get("payer_user_name")
        raw_payer_user_id = payload.get("payer_user_id")
        if raw_payer_user_id is not None:
            try:
                payer_user_id = int(raw_payer_user_id)
            except (TypeError, ValueError):
                return apply_cors(func.HttpResponse("Invalid payer user id", status_code=400))
            if payer_user_id not in group_member_ids:
                return apply_cors(func.HttpResponse("Payer not a member of this group", status_code=403))
        elif payer_user_name:
            payer_user_id = name_to_id.get(payer_user_name.strip().lower())
            if not payer_user_id:
                return apply_cors(func.HttpResponse("Payer not found in group", status_code=400))
        else:
            payer_user_id = trx.payer_user_id
        note = payload.get("note", trx.note)
        splits = payload.get("splits", None)

        splits_provided = splits is not None
        if not splits_provided and payload.get("amount") is not None:
            return apply_cors(func.HttpResponse("Updating amount requires updated splits", status_code=400))

        if splits_provided:
            computed_sum = decimal.Decimal('0.00')
            new_split_objs = []
            for s in splits:
                target_user_id = s.get('user_id')
                if target_user_id is None:
                    user_name = s.get('user_name')
                    if not user_name:
                        return apply_cors(func.HttpResponse("Each split must include user_id or user_name", status_code=400))
                    target_user_id = name_to_id.get(user_name.strip().lower())
                    if not target_user_id:
                        return apply_cors(func.HttpResponse(f"Member {user_name} not found in group", status_code=400))
                else:
                    try:
                        target_user_id = int(target_user_id)
                    except (TypeError, ValueError):
                        return apply_cors(func.HttpResponse("Invalid split user id", status_code=400))
                    if target_user_id not in group_member_ids:
                        return apply_cors(func.HttpResponse("Split member not in group", status_code=403))
                if 'share_amount' in s:
                    sa = decimal.Decimal(str(s['share_amount'])).quantize(cent)
                    sp_decimal = None
                    if s.get('share_percent') is not None:
                        sp_decimal = decimal.Decimal(str(s['share_percent'])).quantize(decimal.Decimal('0.01'))
                elif 'share_percent' in s:
                    sp_decimal = decimal.Decimal(str(s['share_percent'])).quantize(decimal.Decimal('0.01'))
                    sa = (sp_decimal * amount / decimal.Decimal('100')).quantize(cent)
                else:
                    return apply_cors(func.HttpResponse("Each split must have share_amount or share_percent", status_code=400))
                computed_sum += sa
                new_split_objs.append((int(target_user_id), sa, sp_decimal))

            diff = (amount - computed_sum).quantize(cent)
            if diff != decimal.Decimal('0.00'):
                if abs(diff) > tolerance or not new_split_objs:
                    return apply_cors(func.HttpResponse("Splits do not sum to amount", status_code=400))
                uid, sa, sp = new_split_objs[-1]
                adjusted = (sa + diff).quantize(cent)
                if adjusted < decimal.Decimal('0.00'):
                    return apply_cors(func.HttpResponse("Invalid split totals", status_code=400))
                new_split_objs[-1] = (uid, adjusted, sp)
                computed_sum = (computed_sum + diff).quantize(cent)

            if computed_sum != amount:
                return apply_cors(func.HttpResponse("Splits do not sum to amount", status_code=400))

            db.query(Split).filter(Split.transaction_id == trx.id).delete()
            for (uid, sa, sp) in new_split_objs:
                db.add(Split(transaction_id=trx.id, user_id=uid, share_amount=sa, share_percent=sp))

        trx.title = title
        trx.amount = amount
        trx.payer_user_id = payer_user_id
        trx.note = note

        new_splits_snapshot = []
        if splits_provided:
            for (uid, sa, sp) in new_split_objs:
                new_splits_snapshot.append({"user_id": uid, "share": str(sa)})

        new_snapshot = {
            "transaction": {"id": trx.id, "title": trx.title, "amount": str(trx.amount), "payer": trx.payer_user_id},
            "splits": new_splits_snapshot or [{"user_id": s.user_id, "share": str(s.share_amount)} for s in old_splits]
        }

        hist = TransactionHistory(transaction_id=trx.id, group_id=trx.group_id, action='updated',
                                  data=json.dumps({"old": old_snapshot, "new": new_snapshot}),
                                  actor_user_id=user.id)
        db.add(hist)
        db.commit()
        return apply_cors(func.HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json"))
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Failed to update transaction %s", tx_id)
        return apply_cors(func.HttpResponse("DB error", status_code=500))
    finally:
        db.close()
