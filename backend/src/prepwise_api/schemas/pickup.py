from uuid import UUID

from pydantic import BaseModel


class PickupLocationResponse(BaseModel):
    id: UUID
    name: str
    address_line: str
    postal_code: str
    city: str
