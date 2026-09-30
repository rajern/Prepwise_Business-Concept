"""Add authored catalogue translations and explicit assistant pickup selections.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen authored migration data: match existing text precisely; never reseed the catalogue.
MEALS = (
    (
        "Kylling teriyaki med ris",
        "Chicken teriyaki with rice",
        "Saftig kylling med jasminris, brokkoli og gulrot i teriyakisaus.",
        "Tender chicken with jasmine rice, broccoli and carrots in teriyaki sauce.",
    ),
    (
        "Laks med ovnsbakte poteter",
        "Salmon with roasted potatoes",
        "Ovnsbakt laks med småpoteter, grønne bønner og frisk yoghurtdressing.",
        "Oven-baked salmon with baby potatoes, green beans and a fresh yoghurt dressing.",
    ),
    (
        "Tacobowl med karbonadedeig",
        "Lean beef taco bowl",
        "Karbonadedeig, ris, svarte bønner, mais og salsa toppet med cheddar.",
        "Lean minced beef, rice, black beans, sweetcorn and salsa topped with cheddar.",
    ),
    (
        "Kremet kyllingpasta",
        "Creamy chicken pasta",
        "Fullkornspasta med kylling, spinat og en lett kremet parmesansaus.",
        "Wholegrain pasta with chicken, spinach and a light, creamy parmesan sauce.",
    ),
    (
        "Tofu satay med risnudler",
        "Tofu satay with rice noodles",
        "Marinert tofu med risnudler, sprø grønnsaker og peanøttsaus.",
        "Marinated tofu with rice noodles, crunchy vegetables and peanut sauce.",
    ),
    (
        "Falafelbowl med bulgur",
        "Falafel bowl with bulgur",
        "Falafel og bulgur med hummus, tomat, agurk og tahinidressing.",
        "Falafel and bulgur with hummus, tomato, cucumber and tahini dressing.",
    ),
    (
        "Rød thaicurry med kylling",
        "Thai red chicken curry",
        "Kylling og grønnsaker i rød karrisaus med kokosmelk og jasminris.",
        "Chicken and vegetables in a red curry sauce with coconut milk and jasmine rice.",
    ),
    (
        "Kalkunkjøttboller med couscous",
        "Turkey meatballs with couscous",
        "Kalkunkjøttboller, couscous og squash med fyldig tomatsaus.",
        "Turkey meatballs, couscous and courgette with a rich tomato sauce.",
    ),
    (
        "Biff stroganoff med potetmos",
        "Beef stroganoff with mashed potatoes",
        "Mør biff med sopp og løk i kremet saus, servert med potetmos.",
        "Tender beef with mushrooms and onions in a creamy sauce, served with mashed potatoes.",
    ),
    (
        "Middelhavspasta med laks",
        "Mediterranean salmon pasta",
        "Fullkornspasta med laks, tomat, spinat og oliven.",
        "Wholegrain pasta with salmon, tomato, spinach and olives.",
    ),
    (
        "Linsegryte med søtpotet",
        "Lentil and sweet potato stew",
        "Varmende gryte med røde linser, søtpotet, tomat, spinat og kokosmelk.",
        "A warming stew with red lentils, sweet potato, tomato, spinach and coconut milk.",
    ),
    (
        "Stekt ris med egg",
        "Egg fried rice",
        "Stekt jasminris med egg, erter, gulrot, vårløk og soyasaus.",
        "Fried jasmine rice with eggs, peas, carrots, spring onions and soy sauce.",
    ),
)
INGREDIENTS = {
    "Kylling": "Chicken",
    "Jasminris": "Jasmine rice",
    "Brokkoli": "Broccoli",
    "Gulrot": "Carrot",
    "Teriyakisaus": "Teriyaki sauce",
    "Laks": "Salmon",
    "Småpoteter": "Baby potatoes",
    "Grønne bønner": "Green beans",
    "Yoghurt": "Yoghurt",
    "Sitron": "Lemon",
    "Dill": "Dill",
    "Karbonadedeig": "Lean minced beef",
    "Svarte bønner": "Black beans",
    "Mais": "Sweetcorn",
    "Salsa": "Salsa",
    "Cheddar": "Cheddar",
    "Fullkornspasta": "Wholegrain pasta",
    "Spinat": "Spinach",
    "Matfløte": "Cooking cream",
    "Parmesan": "Parmesan",
    "Tofu": "Tofu",
    "Risnudler": "Rice noodles",
    "Rødkål": "Red cabbage",
    "Peanøttsaus": "Peanut sauce",
    "Falafel": "Falafel",
    "Bulgur": "Bulgur",
    "Hummus": "Hummus",
    "Tomat": "Tomato",
    "Agurk": "Cucumber",
    "Tahini": "Tahini",
    "Kokosmelk": "Coconut milk",
    "Rød karripasta": "Red curry paste",
    "Paprika": "Bell pepper",
    "Kalkun": "Turkey",
    "Couscous": "Couscous",
    "Squash": "Courgette",
    "Tomatsaus": "Tomato sauce",
    "Egg": "Egg",
    "Storfekjøtt": "Beef",
    "Poteter": "Potatoes",
    "Sjampinjong": "Mushroom",
    "Rømme": "Sour cream",
    "Løk": "Onion",
    "Sennep": "Mustard",
    "Oliven": "Olives",
    "Røde linser": "Red lentils",
    "Søtpotet": "Sweet potato",
    "Erter": "Peas",
    "Vårløk": "Spring onion",
    "Soyasaus": "Soy sauce",
}
ALLERGENS = {
    "Gluten": "Gluten",
    "Melk": "Milk",
    "Egg": "Egg",
    "Fisk": "Fish",
    "Soya": "Soy",
    "Sesam": "Sesame",
    "Nøtter": "Nuts",
    "Peanøtter": "Peanuts",
    "Sennep": "Mustard",
}


def upgrade() -> None:
    op.add_column("meals", sa.Column("name_en", sa.String(200), nullable=True))
    op.add_column("meals", sa.Column("description_en", sa.Text(), nullable=True))
    op.add_column("ingredients", sa.Column("name_en", sa.String(200), nullable=True))
    op.add_column("allergens", sa.Column("name_en", sa.String(100), nullable=True))
    op.add_column("order_items", sa.Column("meal_name_en", sa.String(200), nullable=True))
    op.add_column("order_confirmations", sa.Column("pickup_start_at", sa.DateTime(timezone=True)))
    op.add_column("order_confirmations", sa.Column("pickup_end_at", sa.DateTime(timezone=True)))
    meals = sa.table(
        "meals",
        sa.column("name", sa.String(200)),
        sa.column("name_en", sa.String(200)),
        sa.column("description", sa.Text()),
        sa.column("description_en", sa.Text()),
    )
    items = sa.table(
        "order_items",
        sa.column("meal_name", sa.String(200)),
        sa.column("meal_name_en", sa.String(200)),
    )
    for name, name_en, description, description_en in MEALS:
        # Normalize only a complete, known English demo entry, and never merge identities.
        norwegian_exists = sa.exists(sa.select(1).where(meals.c.name == name))
        op.execute(
            meals.update()
            .where(
                meals.c.name == name_en, meals.c.description == description_en, ~norwegian_exists
            )
            .values(
                name=name, description=description, name_en=name_en, description_en=description_en
            )
        )
        op.execute(meals.update().where(meals.c.name == name).values(name_en=name_en))
        op.execute(
            meals.update()
            .where(meals.c.name == name, meals.c.description == description)
            .values(description_en=description_en)
        )
        op.execute(items.update().where(items.c.meal_name == name).values(meal_name_en=name_en))
    for table_name, translations in (("ingredients", INGREDIENTS), ("allergens", ALLERGENS)):
        table = sa.table(
            table_name, sa.column("name", sa.String(200)), sa.column("name_en", sa.String(200))
        )
        for name, name_en in translations.items():
            op.execute(table.update().where(table.c.name == name).values(name_en=name_en))


def downgrade() -> None:
    op.drop_column("order_confirmations", "pickup_end_at")
    op.drop_column("order_confirmations", "pickup_start_at")
    op.drop_column("order_items", "meal_name_en")
    op.drop_column("allergens", "name_en")
    op.drop_column("ingredients", "name_en")
    op.drop_column("meals", "description_en")
    op.drop_column("meals", "name_en")
