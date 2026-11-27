"""Request and response shapes for authentication and user management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The finance head can create these personas; never another finance head.
CreatableRole = Literal["employee", "line_manager", "finance_auditor"]


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=64,
        description="Username or work email (case-insensitive).",
    )
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str | None
    role: str
    manager_id: int | None
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(BaseModel):
    # `@` and `+` allowed: the login page sends the work email as the username (team decision).
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._@+-]+$")
    full_name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: CreatableRole
    password: str = Field(min_length=8, max_length=128)
    manager_id: int | None = None
