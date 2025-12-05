import functools
from typing import Callable
from db_sqlite import SessionLocal
from models import User, GroupMember
from auth_utils import decode_access_token
from azure.functions import HttpResponse
from http_utils import apply_cors, preflight_response

def require_auth(func: Callable):
    @functools.wraps(func)
    def wrapper(req, *args, **kwargs):
        if getattr(req, "method", "").upper() == "OPTIONS":
            return preflight_response()
        auth = req.headers.get("Authorization") or req.headers.get("authorization")
        if not auth or not auth.startswith("Bearer "):
            return apply_cors(HttpResponse("Missing Authorization", status_code=401))
        token = auth.split(" ",1)[1].strip()
        try:
            payload = decode_access_token(token)
        except Exception:
            return apply_cors(HttpResponse("Invalid/expired token", status_code=401))
        user_id = int(payload.get("sub"))
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return apply_cors(HttpResponse("User not found", status_code=401))
            setattr(req, "current_user", user)
        finally:
            db.close()
        response = func(req, *args, **kwargs)
        return apply_cors(response)
    return wrapper

def user_in_group(db, user_id, group_id):
    return db.query(GroupMember).filter(GroupMember.group_id==group_id, GroupMember.user_id==user_id).first() is not None

def user_is_admin(db, user_id, group_id):
    user = db.query(User).filter(User.id == user_id).first()
    if user and getattr(user, 'global_admin', False):
        return True
    if group_id is None:
        return False
    gm = db.query(GroupMember).filter(GroupMember.group_id==group_id, GroupMember.user_id==user_id, GroupMember.role=='admin').first()
    return gm is not None
