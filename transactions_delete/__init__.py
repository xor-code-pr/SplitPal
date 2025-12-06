import json, azure.functions as func

from auth_decorator import require_auth, user_is_admin
from db_sqlite import SessionLocal
from http_utils import apply_cors
from logging_utils import ensure_request_logger
from models import Split, Transaction, TransactionHistory
from sqlalchemy.exc import SQLAlchemyError

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    tx_id = req.route_params.get('id') or req.params.get('id')
    if not tx_id:
        ensure_request_logger(req, name=__name__, user=getattr(req, "current_user", None))
        return apply_cors(func.HttpResponse("Missing transaction id", status_code=400))
    user = getattr(req, "current_user")
    log = ensure_request_logger(req, name=__name__, user=user)
    db = SessionLocal()
    try:
        try:
            tx_id_int = int(tx_id)
        except (TypeError, ValueError):
            log.warning("Invalid transaction id", extra={"transaction_id": tx_id})
            return apply_cors(func.HttpResponse("Invalid transaction id", status_code=400))

        log = ensure_request_logger(req, name=__name__, user=user, extra={"transaction_id": tx_id_int})

        trx = db.query(Transaction).filter(Transaction.id == tx_id_int).first()
        if not trx:
            log.warning("Transaction not found for delete")
            return apply_cors(func.HttpResponse("Transaction not found", status_code=404))
        is_admin = user_is_admin(db, user.id, trx.group_id)
        is_creator = trx.created_by == user.id if trx.created_by is not None else False
        if not (is_admin or is_creator):
            log.warning(
                "User not permitted to delete transaction",
                extra={"group_id": trx.group_id, "is_admin": is_admin, "is_creator": is_creator},
            )
            return apply_cors(func.HttpResponse("Only group admins or the transaction creator can delete this transaction", status_code=403))
        hist = TransactionHistory(transaction_id=trx.id, group_id=trx.group_id, action='deleted',
                      data=json.dumps({"transaction_id": trx.id, "title": trx.title, "amount": str(trx.amount)}),
                      actor_user_id=user.id)
        db.add(hist)
        db.query(Split).filter(Split.transaction_id == trx.id).delete()
        db.delete(trx)
        db.commit()
        log.info("Deleted transaction", extra={"group_id": trx.group_id})
        return apply_cors(func.HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json"))
    except SQLAlchemyError as e:
        db.rollback()
        log.exception("Database error while deleting transaction")
        return apply_cors(func.HttpResponse("DB error", status_code=500))
    finally:
        db.close()
