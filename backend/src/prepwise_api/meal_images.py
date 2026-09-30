"""Versioned, illustrative catalogue assets hosted by the frontend, not the API."""

from prepwise_api.models import Meal
from prepwise_api.seed_data import MEALS

MEAL_IMAGE_SLUGS = {
    "Kylling teriyaki med ris": "chicken-teriyaki",
    "Laks med ovnsbakte poteter": "salmon-potatoes",
    "Tacobowl med karbonadedeig": "taco-beef",
    "Kremet kyllingpasta": "creamy-chicken-pasta",
    "Tofu satay med risnudler": "tofu-satay",
    "Falafelbowl med bulgur": "falafel-bulgur",
    "Rød thaicurry med kylling": "red-thai-chicken",
    "Kalkunkjøttboller med couscous": "turkey-couscous",
    "Biff stroganoff med potetmos": "beef-stroganoff",
    "Middelhavspasta med laks": "mediterranean-salmon-pasta",
    "Linsegryte med søtpotet": "lentil-sweet-potato",
    "Stekt ris med egg": "egg-fried-rice",
}
_RECIPES = {seed.name: frozenset(seed.ingredients) for seed in MEALS}


def catalogue_image_url(meal: Meal) -> str | None:
    """Preserve authored URLs; only illustrate an unchanged known ingredient set."""
    if meal.image_url:
        return meal.image_url
    slug = MEAL_IMAGE_SLUGS.get(meal.name)
    if slug and frozenset(item.name for item in meal.ingredients) == _RECIPES[meal.name]:
        return f"/images/meals/{slug}-v1.webp"
    return None
