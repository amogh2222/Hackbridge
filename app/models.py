"""
HackBridge — Pydantic Models
Request/response schemas used across routers.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# ── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    role: str = "participant"


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str
    role: str


# ── AI Endpoints ─────────────────────────────────────────────────────────────

class SkillsRequest(BaseModel):
    bio: str = Field(..., min_length=10, description="Free-text user biography")


class DedupeRequest(BaseModel):
    email: str
    first_name: str
    last_name: str


class AssignRequest(BaseModel):
    hackathon_id: str


class BiasRequest(BaseModel):
    hackathon_id: str


# ── Dashboard ────────────────────────────────────────────────────────────────

class OrganizerMetrics(BaseModel):
    total_active_events: int
    total_participants: int
    total_judges: int
    total_projects: int
    completion_rate: float
    evaluations_completed: int
    bias_flags_detected: int
