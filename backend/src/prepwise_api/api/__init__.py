from prepwise_api.api.admin import router as admin_router
from prepwise_api.api.meals import router as meals_router
from prepwise_api.api.users import router as users_router

__all__ = ["admin_router", "meals_router", "users_router"]
