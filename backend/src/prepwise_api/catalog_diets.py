"""Authored diet metadata for the declared, unchanged portfolio recipes.

Not a medical/allergen guarantee. Unrecognised or changed recipes remain unknown;
never infer a vegetarian label from a name or the absence of a meat keyword.
"""

from typing import Literal

from prepwise_api.models import Meal
from prepwise_api.seed_data import MEALS

DietCategory = Literal["meat", "fish", "vegetarian"]
_CATEGORIES: dict[str, DietCategory] = {
    "Kylling teriyaki med ris": "meat",
    "Laks med ovnsbakte poteter": "fish",
    "Tacobowl med karbonadedeig": "meat",
    "Kremet kyllingpasta": "meat",
    "Tofu satay med risnudler": "vegetarian",
    "Falafelbowl med bulgur": "vegetarian",
    "Rød thaicurry med kylling": "meat",
    "Kalkunkjøttboller med couscous": "meat",
    "Biff stroganoff med potetmos": "meat",
    "Middelhavspasta med laks": "fish",
    "Linsegryte med søtpotet": "vegetarian",
    "Stekt ris med egg": "vegetarian",
}
_RECIPES = {seed.name: frozenset(seed.ingredients) for seed in MEALS}


def catalogue_diet_category(meal: Meal) -> DietCategory | None:
    category = _CATEGORIES.get(meal.name)
    if category and frozenset(item.name for item in meal.ingredients) == _RECIPES[meal.name]:
        return category
    return None
