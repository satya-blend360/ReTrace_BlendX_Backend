from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TokenRequestModel(BaseModel):
    code: str


class TokenModel(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime


class UserInfo(BaseModel):
    id: str
    name: str
    email: str
    roles: Optional[str] = None