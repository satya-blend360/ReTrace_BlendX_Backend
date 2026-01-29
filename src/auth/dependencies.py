from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from src.auth.models import UserInfo
from src.utils.config import JWT_SECRET

authenticate = HTTPBearer()


def create_jwt_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=4))
    to_encode.update({"exp": expire})

    if not JWT_SECRET:
        raise ValueError("JWT_SECRET is not configured")

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def decode_jwt_token(token: str) -> Optional[dict]:
    try:
        if not JWT_SECRET:
            return None
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError:
        return None

def authorize_token(required_role: Optional[str] = None):
    def verify_token(credentials: HTTPAuthorizationCredentials = Depends(authenticate)):
        token = credentials.credentials
        payload = decode_jwt_token(token)

        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token or token expired"
            )

        user = UserInfo(**payload)

        if required_role and user.roles != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: insufficient role"
            )

        return user
    
    return verify_token
