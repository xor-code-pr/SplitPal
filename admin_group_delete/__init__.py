import json, azure.functions as func

from auth_decorator import require_auth, user_is_admin
from db_sqlite import SessionLocal
from logging_utils import ensure_request_logger
from models import Group, GroupMember, Transaction, Split, TransactionHistory

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    group_id = req.route_params.get('id') or req.params.get('id')
    if not group_id:
        ensure_request_logger(req, name=__name__, user=user)
        return func.HttpResponse("Missing group id", status_code=400)
    log = ensure_request_logger(req, name=__name__, user=user, extra={"group_id": group_id})
    db = SessionLocal()
    try:
        numeric_group_id = int(group_id)
        log.debug("Deleting group as admin")
        if not user_is_admin(db, user.id, numeric_group_id):
            log.warning("User lacks admin rights for group")
            return func.HttpResponse("Admin privileges required", status_code=403)
        g = db.query(Group).filter(Group.id == numeric_group_id).first()
        if not g:
            log.warning("Group not found during delete")
            return func.HttpResponse("Group not found", status_code=404)
        # Delete related members, transactions, splits, histories
        db.query(GroupMember).filter(GroupMember.group_id == numeric_group_id).delete()
        txs = db.query(Transaction).filter(Transaction.group_id == numeric_group_id).all()
        for t in txs:
            db.query(Split).filter(Split.transaction_id == t.id).delete()
            db.query(TransactionHistory).filter(TransactionHistory.transaction_id == t.id).delete()
            db.delete(t)
        db.delete(g)
        db.commit()
        log.info("Group deleted", extra={"deleted_transactions": len(txs)})
        return func.HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json")
    finally:
        db.close()
