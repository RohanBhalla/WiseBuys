from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_admin, get_db
from app.models import User, ValueTag
from app.schemas.tag import TagCreate, TagPublic

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagPublic])
def list_tags(db: Session = Depends(get_db), only_active: bool = True) -> list[ValueTag]:
    query = db.query(ValueTag).order_by(ValueTag.label.asc())
    if only_active:
        query = query.filter(ValueTag.is_active.is_(True))
    return query.all()


@router.post("", response_model=TagPublic, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ValueTag:
    if db.query(ValueTag).filter(ValueTag.slug == payload.slug).one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag slug already exists")
    tag = ValueTag(**payload.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag
