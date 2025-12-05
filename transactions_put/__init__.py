import json, decimal, azure.functions as func
from db_sqlite import SessionLocal
from models import Transaction, Split, TransactionHistory, User, GroupMember
from auth_decorator import require_auth, user_in_group
from sqlalchemy.exc import SQLAlchemyError

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    tx_id = req.route_params.get('id') or req.params.get('id')
    if not tx_id:
        return func.HttpResponse("Missing transaction id", status_code=400)
    try:
        payload = req.get_json()
    except:
        return func.HttpResponse("Invalid JSON", status_code=400)

    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        trx = db.query(Transaction).filter(Transaction.id == int(tx_id)).first()
        if not trx:
            return func.HttpResponse("Transaction not found", status_code=404)
        if not user_in_group(db, user.id, trx.group_id):
            return func.HttpResponse("Not a member of this group", status_code=403)

        member_rows = (
            db.query(GroupMember.user_id, User.name)
            .join(User, GroupMember.user_id == User.id)
            .filter(GroupMember.group_id == trx.group_id)
            .all()
        )
        name_to_id = {name.strip().lower(): uid for uid, name in member_rows}

        old_splits = db.query(Split).filter(Split.transaction_id == trx.id).all()
        old_snapshot = {
            "transaction": {"id": trx.id, "title": trx.title, "amount": str(trx.amount), "payer": trx.payer_user_id},
            "splits": [{"user_id": s.user_id, "share": str(s.share_amount)} for s in old_splits]
        }

        title = payload.get("title", trx.title)
        amount = decimal.Decimal(str(payload.get("amount", trx.amount)))
        payer_user_name = payload.get("payer_user_name")
        raw_payer_user_id = payload.get("payer_user_id")
        if raw_payer_user_id is not None:
            try:
                payer_user_id = int(raw_payer_user_id)
            except (TypeError, ValueError):
                return func.HttpResponse("Invalid payer user id", status_code=400)
        elif payer_user_name:
            payer_user_id = name_to_id.get(payer_user_name.strip().lower())
            if not payer_user_id:
                return func.HttpResponse("Payer not found in group", status_code=400)
        else:
            payer_user_id = trx.payer_user_id
        note = payload.get("note", trx.note)
        splits = payload.get("splits", None)

        if splits is not None:
            computed_sum = decimal.Decimal('0.00')
            new_split_objs = []
            for s in splits:
                target_user_id = s.get('user_id')
                if target_user_id is None:
                    user_name = s.get('user_name')
                    if not user_name:
                        return func.HttpResponse("Each split must include user_id or user_name", status_code=400)
                    target_user_id = name_to_id.get(user_name.strip().lower())
                    if not target_user_id:
                        return func.HttpResponse(f"Member {user_name} not found in group", status_code=400)
                else:
                    try:
                        target_user_id = int(target_user_id)
                    except (TypeError, ValueError):
                        return func.HttpResponse("Invalid split user id", status_code=400)
                if 'share_amount' in s:
                    sa = decimal.Decimal(str(s['share_amount']))
                elif 'share_percent' in s:
                    sp = decimal.Decimal(str(s['share_percent']))
                    sa = (sp * amount / decimal.Decimal('100')).quantize(decimal.Decimal('0.01'))
                else:
                    return func.HttpResponse("Each split must have share_amount or share_percent", status_code=400)
                computed_sum += sa
                sp_value = s.get('share_percent')
                sp_decimal = decimal.Decimal(str(sp_value)) if sp_value is not None else None
                new_split_objs.append((int(target_user_id), sa, sp_decimal))

            diff = abs(amount - computed_sum)
            if diff > decimal.Decimal('0.02'):
                return func.HttpResponse("Splits do not sum to amount", status_code=400)

            db.query(Split).filter(Split.transaction_id == trx.id).delete()
            for (uid, sa, sp) in new_split_objs:
                db.add(Split(transaction_id=trx.id, user_id=uid, share_amount=sa, share_percent=sp))

        trx.title = title
        trx.amount = amount
        trx.payer_user_id = payer_user_id
        trx.note = note

        new_splits_snapshot = []
        if splits is not None:
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
        return func.HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json")
    except SQLAlchemyError as e:
        db.rollback()
        return func.HttpResponse("DB error", status_code=500)
    finally:
        db.close()
