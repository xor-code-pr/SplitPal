import json, azure.functions as func
from db_sqlite import SessionLocal
from models import Transaction, TransactionHistory, Split
from auth_decorator import require_auth, user_is_admin
from sqlalchemy.exc import SQLAlchemyError

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    tx_id = req.route_params.get('id') or req.params.get('id')
    if not tx_id:
        return func.HttpResponse("Missing transaction id", status_code=400)
    user = getattr(req, "current_user")
    db = SessionLocal()
    try:
        trx = db.query(Transaction).filter(Transaction.id == int(tx_id)).first()
        if not trx:
            return func.HttpResponse("Transaction not found", status_code=404)
        is_admin = user_is_admin(db, user.id, trx.group_id)
        is_creator = trx.created_by == user.id if trx.created_by is not None else False
        if not (is_admin or is_creator):
            return func.HttpResponse("Only group admins or the transaction creator can delete this transaction", status_code=403)
        hist = TransactionHistory(transaction_id=trx.id, group_id=trx.group_id, action='deleted',
                      data=json.dumps({"transaction_id": trx.id, "title": trx.title, "amount": str(trx.amount)}),
                      actor_user_id=user.id)
        db.add(hist)
        db.query(Split).filter(Split.transaction_id == trx.id).delete()
        db.delete(trx)
        db.commit()
        return func.HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json")
    except SQLAlchemyError as e:
        db.rollback()
        return func.HttpResponse("DB error", status_code=500)
    finally:
        db.close()
