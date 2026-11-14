from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BrowserInfo(BaseModel):
    language: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=100)
    platform: str | None = Field(default=None, max_length=200)
    screen_width: int | None = Field(default=None, ge=0, le=100000)
    screen_height: int | None = Field(default=None, ge=0, le=100000)
    hardware_concurrency: int | None = Field(default=None, ge=1, le=4096)


class CveInfo(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    description: str | None = None
    cvss_score: float | None = Field(default=None, ge=0, le=10)


class ClickEvent(BaseModel):
    event_id: UUID
    fingerprint: str = Field(min_length=64, max_length=64)
    ip: str
    user_agent: str
    browser: BrowserInfo
    cve: CveInfo
    created_at: datetime
