import json, azure.functions as func
from datetime import datetime, timedelta
from db_sqlite import SessionLocal
from models import User, RefreshToken
from auth_utils import (
    hash_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    JWT_EXP,
    JWT_REFRESH_EXP
)
from http_utils import apply_cors, preflight_response

def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()
    try:
        data = req.get_json()
    except:
        return apply_cors(func.HttpResponse("Invalid JSON", status_code=400))
    name = data.get("name"); email = data.get("email"); password = data.get("password")
    if not all([name,email,password]):
        return apply_cors(func.HttpResponse("Missing fields", status_code=400))
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email==email).first():
            return apply_cors(func.HttpResponse("Email already registered", status_code=400))
        u = User(name=name, email=email, password_hash=hash_password(password))
        db.add(u); db.commit(); db.refresh(u)

        access_token = create_access_token(u.id, u.email)
        refresh_token = generate_refresh_token()
        expires_at = datetime.utcnow() + timedelta(seconds=JWT_REFRESH_EXP)

        db.query(RefreshToken).filter(RefreshToken.user_id == u.id).delete()
        db.add(
            RefreshToken(
                user_id=u.id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=expires_at
            )
        )
        db.commit()
        payload = {
            "user": {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "is_admin": bool(getattr(u, "global_admin", False))
            },
            "token": access_token,
            "token_expires_in": JWT_EXP,
            "refresh_token": refresh_token,
            "refresh_expires_in": JWT_REFRESH_EXP
        }
        return apply_cors(func.HttpResponse(json.dumps(payload), status_code=201, mimetype="application/json"))
    finally:
        db.close()
