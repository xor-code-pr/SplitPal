import json, azure.functions as func
from db_sqlite import SessionLocal
from models import Group, GroupMember, Transaction, Split, TransactionHistory
from auth_decorator import require_auth
from auth_decorator import user_is_admin

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    user = getattr(req, "current_user")
    group_id = req.route_params.get('id') or req.params.get('id')
    if not group_id:
        return func.HttpResponse("Missing group id", status_code=400)
    db = SessionLocal()
    try:
        if not user_is_admin(db, user.id, int(group_id)):
            return func.HttpResponse("Admin privileges required", status_code=403)
        g = db.query(Group).filter(Group.id == int(group_id)).first()
        if not g:
            return func.HttpResponse("Group not found", status_code=404)
        # Delete related members, transactions, splits, histories
        db.query(GroupMember).filter(GroupMember.group_id == int(group_id)).delete()
        txs = db.query(Transaction).filter(Transaction.group_id == int(group_id)).all()
        for t in txs:
            db.query(Split).filter(Split.transaction_id == t.id).delete()
            db.query(TransactionHistory).filter(TransactionHistory.transaction_id == t.id).delete()
            db.delete(t)
        db.delete(g)
        db.commit()
        return func.HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json")
    finally:
        db.close()
