"""Auth stub: identify the caller from the X-User-Id header. Replace with real authentication."""
from fastapi import HTTPException, Request

from app.config import USERS


def current_user(request: Request) -> dict | None:
    wanted = request.headers.get("X-User-Id")
    return next((u for u in USERS if u["id"] == wanted), None)


def require_user(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Choose who you are (X-User-Id header).")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "Only an admin can make this change.")
    return user
