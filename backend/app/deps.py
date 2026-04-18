import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise credentials_exc
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_exc
    return user


def require_role(*roles: UserRole):
    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in roles]}",
            )
        return user

    return _checker


def get_current_customer(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.customer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer role required")
    return user


def get_current_vendor(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.vendor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor role required")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


__all__ = [
    "get_db",
    "get_current_user",
    "get_current_customer",
    "get_current_vendor",
    "get_current_admin",
    "require_role",
]
