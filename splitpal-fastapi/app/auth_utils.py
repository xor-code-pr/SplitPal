import os, time, jwt, secrets, hashlib
from passlib.context import CryptContext

JWT_SECRET = os.environ.get("JWT_SECRET", "change_this_in_local")
JWT_ALGO = os.environ.get("JWT_ALGO", "HS256")
JWT_EXP = int(os.environ.get("JWT_EXP_SECONDS", "3600"))
JWT_REFRESH_EXP = int(os.environ.get("JWT_REFRESH_EXP_SECONDS", str(60 * 60 * 24 * 90)))

# Accept legacy bcrypt hashes but create new ones using bcrypt_sha256 to avoid the 72 byte limit.
pwd = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")

def hash_password(p):
    return pwd.hash(p)

def verify_password(p, h):
    scheme = pwd.identify(h)
    secret = p
    truncated = False
    if scheme == "bcrypt":
        secret_bytes = p.encode("utf-8")
        if len(secret_bytes) > 72:
            # Bcrypt trims to 72 bytes; mimic that before calling into the backend.
            secret = secret_bytes[:72].decode("utf-8", errors="ignore")
            truncated = True
    verified = pwd.verify(secret, h)
    new_hash = None
    if verified and (scheme != "bcrypt_sha256" or truncated):
        new_hash = hash_password(p)
    return verified, new_hash

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
