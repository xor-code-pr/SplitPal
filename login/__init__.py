import json, azure.functions as func
from datetime import datetime, timedelta

from auth_utils import (
    JWT_EXP,
    JWT_REFRESH_EXP,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from db_sqlite import SessionLocal
from http_utils import apply_cors, preflight_response
from logging_utils import ensure_request_logger
from models import RefreshToken, User

def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()
    log = ensure_request_logger(req, name=__name__)
    try:
        data = req.get_json()
    except Exception:
        log.warning("Login received invalid JSON")
        return apply_cors(func.HttpResponse("Invalid JSON", status_code=400))
    email = data.get("email"); password = data.get("password")
    log = ensure_request_logger(req, name=__name__, user_email=email)
    if not all([email,password]):
        log.warning("Login missing required fields")
        return apply_cors(func.HttpResponse("Missing fields", status_code=400))
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email==email).first()
        verified = False
        new_hash = None
        if user:
            verified, new_hash = verify_password(password, user.password_hash)
        if not user or not verified:
            log.warning("Invalid credentials", extra={"email": email})
            return apply_cors(func.HttpResponse("Invalid credentials", status_code=401))
        if new_hash:
            user.password_hash = new_hash
            db.add(user)
        access_token = create_access_token(user.id, user.email)
        refresh_token = generate_refresh_token()
        expires_at = datetime.utcnow() + timedelta(seconds=JWT_REFRESH_EXP)

        db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
        db.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=expires_at
            )
        )
        db.commit()
        log = ensure_request_logger(req, name=__name__, user=user)
        log.info("User logged in", extra={"user_id": user.id})
        payload = {
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "is_admin": bool(getattr(user, "global_admin", False))
            },
            "token": access_token,
            "token_expires_in": JWT_EXP,
            "refresh_token": refresh_token,
            "refresh_expires_in": JWT_REFRESH_EXP
        }
        return apply_cors(func.HttpResponse(json.dumps(payload), status_code=200, mimetype="application/json"))
    finally:
        db.close()
