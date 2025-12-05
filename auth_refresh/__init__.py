import json
from datetime import datetime, timedelta
import azure.functions as func
from azure.functions import HttpResponse

from db_sqlite import SessionLocal
from models import RefreshToken, User
from auth_utils import (
    create_access_token,
    hash_refresh_token,
    JWT_EXP,
    JWT_REFRESH_EXP
)
from http_utils import apply_cors, preflight_response


def _unauthorized(message: str) -> HttpResponse:
    return apply_cors(HttpResponse(message, status_code=401))


def main(req: func.HttpRequest) -> HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()

    try:
        data = req.get_json()
    except Exception:
        return apply_cors(HttpResponse("Invalid JSON", status_code=400))

    raw_refresh = (data or {}).get("refresh_token")
    if not raw_refresh:
        return apply_cors(HttpResponse("Missing refresh_token", status_code=400))

    token_hash = hash_refresh_token(raw_refresh)
    db = SessionLocal()
    try:
        token_row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if not token_row or token_row.revoked:
            return _unauthorized("Invalid refresh token")

        now = datetime.utcnow()
        if token_row.expires_at <= now:
            token_row.revoked = True
            db.commit()
            return _unauthorized("Refresh token expired")

        user = db.query(User).filter(User.id == token_row.user_id).first()
        if not user:
            token_row.revoked = True
            db.commit()
            return _unauthorized("User not found")

        token_row.expires_at = now + timedelta(seconds=JWT_REFRESH_EXP)

        access_token = create_access_token(user.id, user.email)
        db.commit()

        payload = {
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "is_admin": bool(getattr(user, "global_admin", False))
            },
            "token": access_token,
            "token_expires_in": JWT_EXP,
            "refresh_token": raw_refresh,
            "refresh_expires_in": JWT_REFRESH_EXP
        }
        return apply_cors(HttpResponse(json.dumps(payload), status_code=200, mimetype="application/json"))
    except Exception:
        db.rollback()
        return apply_cors(HttpResponse("Unable to refresh token", status_code=500))
    finally:
        db.close()
