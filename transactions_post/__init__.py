import json, decimal, logging, azure.functions as func
from db_sqlite import SessionLocal
from models import Transaction, Split, TransactionHistory, User, GroupMember
from auth_decorator import require_auth, user_in_group
from sqlalchemy.exc import SQLAlchemyError
from http_utils import apply_cors

logger = logging.getLogger(__name__)

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = req.get_json()
    except:
        return apply_cors(func.HttpResponse("Invalid JSON", status_code=400))

    user = getattr(req, "current_user")
    group_id = payload.get("group_id") or req.route_params.get("group_id")
    title = payload.get("title")
    amount = payload.get("amount")
    payer_user_id = payload.get("payer_user_id")
    payer_user_name = payload.get("payer_user_name")
    note = payload.get("note", "")
    splits = payload.get("splits", [])

    if not group_id or amount is None or not splits:
        return apply_cors(func.HttpResponse("Missing required fields", status_code=400))

    try:
        group_id_int = int(group_id)
    except (TypeError, ValueError):
        return apply_cors(func.HttpResponse("Invalid group id", status_code=400))

    db = SessionLocal()
    try:
        if not user_in_group(db, user.id, group_id_int):
            return apply_cors(func.HttpResponse("Not a member of this group", status_code=403))

        member_rows = (
            db.query(GroupMember.user_id, User.name)
            .join(User, GroupMember.user_id == User.id)
            .filter(GroupMember.group_id == group_id_int)
            .all()
        )
        name_to_id = {name.strip().lower(): uid for uid, name in member_rows}
        group_member_ids = {uid for uid, _ in member_rows}

        if payer_user_id is None:
            if not payer_user_name:
                return apply_cors(func.HttpResponse("Missing payer information", status_code=400))
            payer_user_id = name_to_id.get(payer_user_name.strip().lower())
            if not payer_user_id:
                return apply_cors(func.HttpResponse("Payer not found in group", status_code=400))
        else:
            try:
                payer_user_id = int(payer_user_id)
            except (TypeError, ValueError):
                return apply_cors(func.HttpResponse("Invalid payer user id", status_code=400))
            if payer_user_id not in group_member_ids:
                return apply_cors(func.HttpResponse("Payer not a member of this group", status_code=403))

        cent = decimal.Decimal('0.01')
        tolerance = decimal.Decimal('0.01')
        amt = decimal.Decimal(str(amount)).quantize(cent)
        computed = decimal.Decimal('0.00')
        split_objs = []
        for s in splits:
            target_user_id = s.get('user_id')
            if target_user_id is None:
                user_name = s.get('user_name')
                if not user_name:
                    return apply_cors(func.HttpResponse("Each split must include user_id or user_name", status_code=400))
                target_user_id = name_to_id.get(user_name.strip().lower())
                if not target_user_id:
                    return apply_cors(func.HttpResponse(f"Member {user_name} not found in group", status_code=400))
            if 'share_amount' in s:
                sa = decimal.Decimal(str(s['share_amount'])).quantize(cent)
                sp_decimal = None
                if s.get('share_percent') is not None:
                    sp_decimal = decimal.Decimal(str(s['share_percent'])).quantize(decimal.Decimal('0.01'))
            elif 'share_percent' in s:
                sp_decimal = decimal.Decimal(str(s['share_percent'])).quantize(decimal.Decimal('0.01'))
                sa = (sp_decimal * amt / decimal.Decimal('100')).quantize(cent)
            else:
                return apply_cors(func.HttpResponse("Each split must have share_amount or share_percent", status_code=400))
            if int(target_user_id) not in group_member_ids:
                return apply_cors(func.HttpResponse("Split member not in group", status_code=403))
            computed += sa
            split_objs.append((int(target_user_id), sa, sp_decimal))

        diff = (amt - computed).quantize(cent)
        if diff != decimal.Decimal('0.00'):
            if abs(diff) > tolerance or not split_objs:
                return apply_cors(func.HttpResponse("Splits do not sum to amount", status_code=400))
            uid, sa, sp = split_objs[-1]
            adjusted = (sa + diff).quantize(cent)
            if adjusted < decimal.Decimal('0.00'):
                return apply_cors(func.HttpResponse("Invalid split totals", status_code=400))
            split_objs[-1] = (uid, adjusted, sp)
            computed = (computed + diff).quantize(cent)

        if computed != amt:
            return apply_cors(func.HttpResponse("Splits do not sum to amount", status_code=400))

        trx = Transaction(
            group_id=group_id_int,
            title=title,
            amount=amt,
            payer_user_id=payer_user_id,
            note=note,
            created_by=user.id,
        )
        db.add(trx); db.flush()
        for (uid, sa, sp) in split_objs:
            db.add(Split(transaction_id=trx.id, user_id=uid, share_amount=sa, share_percent=sp))
        hist = TransactionHistory(transaction_id=trx.id, group_id=group_id_int, action='created', data=json.dumps({"title": title, "amount": str(amt)}), actor_user_id=user.id)
        db.add(hist)
        db.commit()
        return apply_cors(func.HttpResponse(json.dumps({"ok": True, "transaction_id": trx.id}), status_code=201, mimetype="application/json"))
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to create transaction for group %s", group_id)
        return apply_cors(func.HttpResponse("DB error", status_code=500))
    finally:
        db.close()
