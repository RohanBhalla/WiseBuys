from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserRole
from app.security import hash_password


def bootstrap_admin(db: Session) -> User | None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return None

    existing = db.query(User).filter(User.email == settings.bootstrap_admin_email).one_or_none()
    if existing:
        return existing

    admin = User(
        email=settings.bootstrap_admin_email,
        password_hash=hash_password(settings.bootstrap_admin_password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
