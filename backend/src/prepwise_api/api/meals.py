from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from prepwise_api.api.service_errors import raise_service_http_error
from prepwise_api.database import get_session
from prepwise_api.schemas import MealDetailResponse, MealResponse
from prepwise_api.services import ApplicationServiceError
from prepwise_api.services.catalog import get_meal_details, search_available_meals
from prepwise_api.services.localization import Language

router = APIRouter(prefix="/api/meals", tags=["meals"])


@router.get("", response_model=list[MealResponse])
def list_available_meals(
    session: Annotated[Session, Depends(get_session)],
    lang: Language = "no",
) -> list[MealResponse]:
    """Return the public meal catalogue from PostgreSQL."""
    return search_available_meals(session, lang=lang)


@router.get("/{meal_id}", response_model=MealDetailResponse)
def get_meal(
    meal_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    lang: Language = "no",
) -> MealDetailResponse:
    """Return one meal, including a clear current availability state."""
    try:
        return get_meal_details(session, meal_id, lang=lang)
    except ApplicationServiceError as error:
        raise_service_http_error(error)
