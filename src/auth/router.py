from datetime import timedelta, datetime

import msal
import httpx
from fastapi import APIRouter, HTTPException, status, Depends

from src.auth.dependencies import create_jwt_token
from src.auth.models import TokenModel, TokenRequestModel, UserInfo
from src.utils.config import SSO_CLIENT_ID, SSO_TENANT_ID, SSO_CLIENT_SECRET, REDIRECT_URI
from src.auth.dependencies import authorize_token

router = APIRouter()


@router.post("/token", response_model=TokenModel)
async def token(token_request: TokenRequestModel):
    token_expiry_hours = 24*12
    token_expiry_at = datetime.utcnow() + timedelta(hours=token_expiry_hours)

    app = msal.ConfidentialClientApplication(
        SSO_CLIENT_ID, authority=f"https://login.microsoftonline.com/{SSO_TENANT_ID}",
        client_credential=SSO_CLIENT_SECRET
    )

    result = app.acquire_token_by_authorization_code(
        token_request.code, scopes=["User.Read"], redirect_uri=REDIRECT_URI
    )

    # print("result", result)

    if "access_token" not in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to acquire token")

    access_token = result["access_token"]

    # Call Graph API to get user details
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to fetch user details")
        user_data = response.json()
    print(user_data)
    user = UserInfo(
        id=user_data["id"],
        name=user_data["displayName"],
        email=user_data["userPrincipalName"].lower()
    )

    # Create JWT token with user details
    jwt_token = create_jwt_token(user.dict(), expires_delta=timedelta(hours=token_expiry_hours))

    return {"access_token": jwt_token, "token_type": "bearer", "expires_at": token_expiry_at}



####_______________USER________________####
@router.get("/users/me")
async def user_info(current_user: UserInfo = Depends(authorize_token())):
    return current_user