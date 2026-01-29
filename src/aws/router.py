from fastapi import APIRouter, UploadFile, File, Body, Form
from pydantic import BaseModel
from uuid import uuid4
import tempfile, os, json
from typing import Optional

from dotenv import load_dotenv
from src.utils import extract_candidates

# from src.utils.embed_and_upsert import embed, upsert_row, load_snowflake_env
from src.aws.service import embed
import snowflake.connector

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets


load_dotenv()

router = APIRouter()

# Health
@router.get("/health")
async def health():
    return {"status": "ok", "service": "AWS Resume Agent Active"}


security = HTTPBasic()


def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "password123")

    # correct_username = secrets.compare_digest(credentials.username, os.getenv("API_USER"))
    # correct_password = secrets.compare_digest(credentials.password, os.getenv("API_PASS"))

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


# --------------------------
# 1️⃣ Resume Parser
# --------------------------
@router.post("/parse-resume")
async def parse_resume(
    file: UploadFile = File(None),
    text: str = Form(None),
    sections: dict = Body(None),
    authorized: bool = Depends(authenticate)
):
    """
    Accepts:
    - PDF/DOC files
    - raw resume text
    - structured sections
    """

    try:
        if sections:
            raw_text = "\n".join(sections.values())
            parsed = extract_candidates.call_bedrock_claude(raw_text)
            return {"success": True, "data": extract_candidates.normalize_record(parsed)}

        if text:
            parsed = extract_candidates.call_bedrock_claude(text)
            return {"success": True, "data": extract_candidates.normalize_record(parsed)}

        if file:
            temp_path = os.path.join(tempfile.gettempdir(), f"{uuid4()}_{file.filename}")
            contents = await file.read()
            with open(temp_path, "wb") as f:
                f.write(contents)

            record = extract_candidates.process_resume(temp_path)
            os.remove(temp_path)
            return {"success": True, "data": record}

        return {"success": False, "error": "Missing file/text/sections"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# --------------------------
# 2️⃣ Embedding Only
# --------------------------
@router.post("/embed")
async def embed_candidate(data: dict = Body(...),authorized: bool = Depends(authenticate)):
    if "summary_text" not in data:
        return {"success": False, "error": "Missing 'summary_text'"}

    try:
        vector = embed(data["summary_text"])
        return {"success": True, "dimensions": len(vector), "embedding": vector}
    except Exception as e:
        return {"success": False, "error": str(e)}


