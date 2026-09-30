import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from prepwise_api.api.admin_meals import _admin_meal_response
from prepwise_api.meal_images import MEAL_IMAGE_SLUGS, catalogue_image_url
from prepwise_api.models import Base, Meal
from prepwise_api.seed import seed_database
from prepwise_api.seed_data import MEALS
from prepwise_api.services.catalog import get_meal_details, search_available_meals


def test_every_seed_recipe_has_a_shipped_webp() -> None:
    assert set(MEAL_IMAGE_SLUGS) == {seed.name for seed in MEALS}
    assert len(set(MEAL_IMAGE_SLUGS.values())) == 12
    assets = Path(__file__).resolve().parents[2] / "frontend" / "public" / "images" / "meals"
    config = json.loads((assets.parents[1] / "staticwebapp.config.json").read_text())
    assert "/images/*" in config["navigationFallback"]["exclude"]
    for slug in MEAL_IMAGE_SLUGS.values():
        image = assets / f"{slug}-v1.webp"
        content = image.read_bytes()
        assert content[:4] == b"RIFF" and content[8:12] == b"WEBP", image.name
        assert 10_000 < len(content) < 300_000, image.name


def test_images_are_bilingual_read_only_and_preserve_admin_edits() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    seed_database(engine)
    with Session(engine) as session:
        norwegian = search_available_meals(session, lang="no")
        english = search_available_meals(session, lang="en")
        assert len(norwegian) == len(english) == 12
        no_images = {meal.id: meal.image_url for meal in norwegian}
        assert no_images == {meal.id: meal.image_url for meal in english}
        assert all(url and url.endswith("-v1.webp") for url in no_images.values())
        meal = session.scalars(select(Meal)).first()
        assert meal is not None
        assert get_meal_details(session, meal.id).image_url == no_images[meal.id]
        assert meal.image_url is None  # Publication does not backfill/reseed business data.
        assert _admin_meal_response(meal).image_url is None
        meal.image_url = "https://example.invalid/authored.jpg"
        assert catalogue_image_url(meal) == meal.image_url
        assert _admin_meal_response(meal).image_url == meal.image_url
        meal.image_url = None
        meal.ingredients = meal.ingredients[:-1]
        assert catalogue_image_url(meal) is None
        meal.name = "Custom meal"
        assert catalogue_image_url(meal) is None
        session.rollback()
    engine.dispose()
