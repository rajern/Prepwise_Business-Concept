from uuid import UUID

from pydantic import BaseModel

from prepwise_api.models import UserRole


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str | None
    display_name: str | None
    role: UserRole
