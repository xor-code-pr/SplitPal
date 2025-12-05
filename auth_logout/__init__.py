import json
import azure.functions as func
from azure.functions import HttpResponse

from db_sqlite import SessionLocal
from models import RefreshToken
from auth_utils import hash_refresh_token
from http_utils import apply_cors, preflight_response


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
        if token_row:
            token_row.revoked = True
            db.commit()
        return apply_cors(HttpResponse(json.dumps({"ok": True}), status_code=200, mimetype="application/json"))
    except Exception:
        db.rollback()
        return apply_cors(HttpResponse("Unable to logout", status_code=500))
    finally:
        db.close()
