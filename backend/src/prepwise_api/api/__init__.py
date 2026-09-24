from prepwise_api.api.admin import router as admin_router
from prepwise_api.api.cart import router as cart_router
from prepwise_api.api.meals import router as meals_router
from prepwise_api.api.orders import router as orders_router
from prepwise_api.api.pickup_locations import router as pickup_locations_router
from prepwise_api.api.users import router as users_router

__all__ = [
    "admin_router",
    "cart_router",
    "meals_router",
    "orders_router",
    "pickup_locations_router",
    "users_router",
]
