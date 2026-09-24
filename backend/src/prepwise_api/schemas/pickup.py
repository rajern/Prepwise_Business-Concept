from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PickupLocationResponse(BaseModel):
    id: UUID
    name: str
    address_line: str
    postal_code: str
    city: str


class PickupLocationAdminResponse(PickupLocationResponse):
    active: bool


class PickupLocationAdminWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    address_line: str = Field(min_length=1, max_length=255)
    postal_code: str = Field(pattern=r"^\d{4}$")
    city: str = Field(min_length=1, max_length=100)
    active: bool = True

    @field_validator("name", "address_line", "postal_code", "city")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped
