import json

import azure.functions as func
from azure.functions import HttpResponse

from auth_utils import hash_refresh_token
from db_sqlite import SessionLocal
from http_utils import apply_cors, preflight_response
from logging_utils import ensure_request_logger
from models import RefreshToken


def main(req: func.HttpRequest) -> HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()

    log = ensure_request_logger(req, name=__name__)
    try:
        data = req.get_json()
    except Exception:
        log.warning("Logout received invalid JSON")
        return apply_cors(HttpResponse("Invalid JSON", status_code=400))

    raw_refresh = (data or {}).get("refresh_token")
    if not raw_refresh:
        log.warning("Logout missing refresh token")
        return apply_cors(HttpResponse("Missing refresh_token", status_code=400))

    token_hash = hash_refresh_token(raw_refresh)
    db = SessionLocal()
    try:
        token_row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if token_row:
            log = ensure_request_logger(req, name=__name__, user_id=token_row.user_id)
            token_row.revoked = True
            db.commit()
            log.info("Revoked refresh token on logout")
        return apply_cors(HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json"))
    except Exception:
        db.rollback()
        log.exception("Failed to revoke refresh token during logout")
        return apply_cors(HttpResponse("Unable to logout", status_code=500))
    finally:
        db.close()
