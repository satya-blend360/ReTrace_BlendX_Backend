from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class Job(BaseModel):
    job_id: str
    job_title: Optional[str]
    location: Optional[str]
    experience_level: Optional[str]
    jd_text: Optional[str]
    updated_at: Optional[datetime]

class MatchedCandidate(BaseModel):
    job_id: str
    candidate_id: str
    name: Optional[str]
    location: Optional[str]
    availability: Optional[str]
    years_total: Optional[float]
    match_score: Optional[float]
    candidate_updated_on: Optional[datetime]
