from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_name: str = Field(min_length=2, max_length=160)
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("organization_name", "full_name", "email")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized.count("@") != 1 or "." not in normalized.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        return normalized


class SigninRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str


class AuthUserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    organization: OrganizationResponse


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=160)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        return value.strip()


class SessionResponse(BaseModel):
    id: UUID
    current: bool
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
