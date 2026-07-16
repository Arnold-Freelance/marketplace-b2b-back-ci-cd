import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.api.deps import get_db, get_factory
from app.core.enums import UserStatus

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    factory = get_factory(db)
    user = factory.user_repo.get_by_id(int(user_id))
    if user.status != UserStatus.active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user
