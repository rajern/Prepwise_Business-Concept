from typing import Annotated

from fastapi import APIRouter, Depends

from prepwise_api.auth import require_admin
from prepwise_api.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/access")
def verify_admin_access(
    user: Annotated[User, Depends(require_admin)],
) -> dict[str, str]:
    """Provide a minimal protected endpoint for authorization verification."""
    return {"status": "ok", "role": user.role.value}
