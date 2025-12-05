import os, time, jwt, secrets, hashlib
from passlib.context import CryptContext

JWT_SECRET = os.environ.get("JWT_SECRET", "change_this_in_local")
JWT_ALGO = os.environ.get("JWT_ALGO", "HS256")
JWT_EXP = int(os.environ.get("JWT_EXP_SECONDS", "3600"))
JWT_REFRESH_EXP = int(os.environ.get("JWT_REFRESH_EXP_SECONDS", str(60 * 60 * 24 * 90)))

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p):
    return pwd.hash(p)

def verify_password(p, h):
    return pwd.verify(p, h)

def create_access_token(user_id, email):
    now = int(time.time())
    payload = {"sub": str(user_id), "email": email, "iat": now, "exp": now + JWT_EXP}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_access_token(token):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])

def generate_refresh_token():
    # 48 bytes -> ~64 chars URL-safe string
    return secrets.token_urlsafe(48)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
