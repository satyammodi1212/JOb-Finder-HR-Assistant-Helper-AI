"""Passwords (scrypt), signed login tokens (HMAC) and role checks. No raw passwords are stored or logged."""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, Header, HTTPException

from . import db
from .config import SECRET_KEY, TOKEN_HOURS


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return salt.hex() + "$" + h.hex()


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex()
        return hmac.compare_digest(got, h)
    except Exception:
        return False


def make_token(uid: str, role: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"uid": uid, "role": role, "exp": int(time.time()) + TOKEN_HOURS * 3600}).encode()).decode()
    return payload + "." + hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def current_user(authorization: str | None = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in")
    try:
        payload, sig = authorization[7:].rsplit(".", 1)
        good = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if data["exp"] < time.time():
            raise ValueError
    except Exception:
        raise HTTPException(401, "Session expired, please log in again")
    rows = db.run("SELECT id,email,name,role,phone,skills,experience_years,location FROM users WHERE id=?", (data["uid"],), fetch=True)
    if not rows:
        raise HTTPException(401, "Unknown user")
    return rows[0]


def hr_user(u=Depends(current_user)):
    if u["role"] != "hr":
        raise HTTPException(403, "HR access only")
    return u


def candidate_user(u=Depends(current_user)):
    if u["role"] != "candidate":
        raise HTTPException(403, "Candidate access only")
    return u
