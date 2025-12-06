import functools
from typing import Callable

from azure.functions import HttpResponse

from auth_utils import decode_access_token
from db_sqlite import SessionLocal
from http_utils import apply_cors, preflight_response
from logging_utils import ensure_request_logger, get_request_logger
from models import GroupMember, User


_AUTH_LOGGER_NAME = __name__

def require_auth(func: Callable):
    @functools.wraps(func)
    def wrapper(req, *args, **kwargs):
        log = get_request_logger(_AUTH_LOGGER_NAME, req=req)
        if getattr(req, "method", "").upper() == "OPTIONS":
            log.debug("Skipping auth for OPTIONS preflight")
            return preflight_response()

        auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            log.warning("Missing Authorization header")
            return apply_cors(HttpResponse("Missing Authorization", status_code=401))

        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_access_token(token)
        except Exception as exc:
            log.warning(
                "Token validation failed",
                extra={"error": exc.__class__.__name__},
            )
            return apply_cors(HttpResponse("Invalid/expired token", status_code=401))

        raw_user_id = payload.get("sub")
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            log.warning("Token subject is missing or invalid", extra={"token_sub": raw_user_id})
            return apply_cors(HttpResponse("Invalid/expired token", status_code=401))

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                log.warning("Token subject not found", extra={"token_sub": user_id})
                return apply_cors(HttpResponse("User not found", status_code=401))
            setattr(req, "current_user", user)
        finally:
            db.close()

        log = ensure_request_logger(req, name=func.__module__, user=user)
        try:
            response = func(req, *args, **kwargs)
        except Exception:
            log.exception("Unhandled exception in handler", extra={"handler": func.__name__})
            raise

        status_code = getattr(response, "status_code", None)
        if status_code is not None and status_code >= 400:
            log.warning(
                "Request completed with non-success status",
                extra={"handler": func.__name__, "status_code": status_code},
            )
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
