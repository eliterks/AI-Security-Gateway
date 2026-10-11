"""Self-contained demo auth helpers. Prefer a maintained JWT library in production."""
import base64
import hashlib
import hmac
import json
import os
import time

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + _b64url(salt) + "$" + _b64url(derived)

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_text, expected_text = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = _unb64url(salt_text)
        expected = _unb64url(expected_text)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def create_access_token(username: str, secret: str, minutes: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": username, "iat": now, "exp": now + minutes * 60}
    head = _b64url(json.dumps(header, separators=(",", ":")).encode())
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = (head + "." + body).encode("ascii")
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return head + "." + body + "." + _b64url(signature)

def verify_access_token(token: str, secret: str):
    try:
        head, body, signature = token.split(".")
        header = json.loads(_unb64url(head))
        payload = json.loads(_unb64url(body))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return None
        expected = hmac.new(
            secret.encode(), (head + "." + body).encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _unb64url(signature)):
            return None
        if not payload.get("sub") or int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
