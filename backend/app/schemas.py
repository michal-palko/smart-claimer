from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class TimeEntryCreate(BaseModel):
    uloha: str
    datum: date
    hodiny: int = Field(..., ge=0)
    minuty: int = Field(..., ge=0, le=59)
    jira: Optional[str] = None
    popis: Optional[str] = None
    autor: str  # Add autor to the create schema
    jira_name: Optional[str] = None
    uloha_name: Optional[str] = None

class TimeEntryResponse(TimeEntryCreate):
    id: int
    autor: str
    created_at: datetime
    modified_at: datetime
    submitted_to_metaapp_at: Optional[datetime] = None
    jira_name: Optional[str] = None
    uloha_name: Optional[str] = None
    metaapp_vykaz_id: Optional[int] = None

    class Config:
        orm_mode = True

class TemplateBase(BaseModel):
    name: str
    uloha: Optional[str] = None
    autor: str
    hodiny: Optional[str] = None
    minuty: Optional[str] = None
    jira: Optional[str] = None
    popis: Optional[str] = None

class TemplateCreate(TemplateBase):
    pass

class TemplateResponse(TemplateBase):
    id: int
    class Config:
        orm_mode = True

class JiraIssue(BaseModel):
    key: str
    summary: Optional[str] = None
    parent_key: Optional[str] = None
    parent_summary: Optional[str] = None
    parent_color: Optional[str] = None
