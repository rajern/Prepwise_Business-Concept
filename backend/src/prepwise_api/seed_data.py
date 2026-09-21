from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AllergenSeed:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class PickupLocationSeed:
    name: str
    address_line: str
    postal_code: str
    city: str = "Oslo"


@dataclass(frozen=True, slots=True)
class MealSeed:
    name: str
    description: str
    price_nok: Decimal
    calories: int
    protein_grams: Decimal
    carbohydrate_grams: Decimal
    fat_grams: Decimal
    ingredients: tuple[str, ...]
    allergen_codes: tuple[str, ...] = ()
    image_url: str | None = None


ALLERGENS = (
    AllergenSeed("gluten", "Gluten"),
    AllergenSeed("milk", "Melk"),
    AllergenSeed("egg", "Egg"),
    AllergenSeed("fish", "Fisk"),
    AllergenSeed("soy", "Soya"),
    AllergenSeed("sesame", "Sesam"),
    AllergenSeed("nuts", "Nøtter"),
    AllergenSeed("peanuts", "Peanøtter"),
    AllergenSeed("mustard", "Sennep"),
)

PICKUP_LOCATIONS = (
    PickupLocationSeed("Prepwise Grünerløkka", "Thorvald Meyers gate 35", "0555"),
    PickupLocationSeed("Prepwise Majorstuen", "Kirkeveien 64B", "0364"),
    PickupLocationSeed("Prepwise Bjørvika", "Dronning Eufemias gate 30", "0191"),
    PickupLocationSeed("Prepwise Nydalen", "Nydalsveien 33", "0484"),
)

MEALS = (
    MealSeed(
        name="Kylling teriyaki med ris",
        description="Saftig kylling med jasminris, brokkoli og gulrot i teriyakisaus.",
        price_nok=Decimal("129.00"),
        calories=585,
        protein_grams=Decimal("43.00"),
        carbohydrate_grams=Decimal("68.00"),
        fat_grams=Decimal("14.00"),
        ingredients=("Kylling", "Jasminris", "Brokkoli", "Gulrot", "Teriyakisaus"),
        allergen_codes=("gluten", "soy"),
    ),
    MealSeed(
        name="Laks med ovnsbakte poteter",
        description="Ovnsbakt laks med småpoteter, grønne bønner og frisk yoghurtdressing.",
        price_nok=Decimal("149.00"),
        calories=620,
        protein_grams=Decimal("39.00"),
        carbohydrate_grams=Decimal("48.00"),
        fat_grams=Decimal("29.00"),
        ingredients=(
            "Laks",
            "Småpoteter",
            "Grønne bønner",
            "Yoghurt",
            "Sitron",
            "Dill",
        ),
        allergen_codes=("fish", "milk"),
    ),
    MealSeed(
        name="Tacobowl med karbonadedeig",
        description="Karbonadedeig, ris, svarte bønner, mais og salsa toppet med cheddar.",
        price_nok=Decimal("135.00"),
        calories=655,
        protein_grams=Decimal("42.00"),
        carbohydrate_grams=Decimal("72.00"),
        fat_grams=Decimal("21.00"),
        ingredients=(
            "Karbonadedeig",
            "Jasminris",
            "Svarte bønner",
            "Mais",
            "Salsa",
            "Cheddar",
        ),
        allergen_codes=("milk",),
    ),
    MealSeed(
        name="Kremet kyllingpasta",
        description="Fullkornspasta med kylling, spinat og en lett kremet parmesansaus.",
        price_nok=Decimal("139.00"),
        calories=670,
        protein_grams=Decimal("48.00"),
        carbohydrate_grams=Decimal("71.00"),
        fat_grams=Decimal("22.00"),
        ingredients=("Kylling", "Fullkornspasta", "Spinat", "Matfløte", "Parmesan"),
        allergen_codes=("gluten", "milk"),
    ),
    MealSeed(
        name="Tofu satay med risnudler",
        description="Marinert tofu med risnudler, sprø grønnsaker og peanøttsaus.",
        price_nok=Decimal("125.00"),
        calories=610,
        protein_grams=Decimal("27.00"),
        carbohydrate_grams=Decimal("74.00"),
        fat_grams=Decimal("24.00"),
        ingredients=("Tofu", "Risnudler", "Rødkål", "Gulrot", "Peanøttsaus"),
        allergen_codes=("peanuts", "soy"),
    ),
    MealSeed(
        name="Falafelbowl med bulgur",
        description="Falafel og bulgur med hummus, tomat, agurk og tahinidressing.",
        price_nok=Decimal("119.00"),
        calories=590,
        protein_grams=Decimal("22.00"),
        carbohydrate_grams=Decimal("78.00"),
        fat_grams=Decimal("21.00"),
        ingredients=("Falafel", "Bulgur", "Hummus", "Tomat", "Agurk", "Tahini"),
        allergen_codes=("gluten", "sesame"),
    ),
    MealSeed(
        name="Rød thaicurry med kylling",
        description="Kylling og grønnsaker i rød karrisaus med kokosmelk og jasminris.",
        price_nok=Decimal("139.00"),
        calories=640,
        protein_grams=Decimal("40.00"),
        carbohydrate_grams=Decimal("69.00"),
        fat_grams=Decimal("23.00"),
        ingredients=(
            "Kylling",
            "Jasminris",
            "Kokosmelk",
            "Rød karripasta",
            "Paprika",
            "Brokkoli",
        ),
    ),
    MealSeed(
        name="Kalkunkjøttboller med couscous",
        description="Kalkunkjøttboller, couscous og squash med fyldig tomatsaus.",
        price_nok=Decimal("135.00"),
        calories=600,
        protein_grams=Decimal("44.00"),
        carbohydrate_grams=Decimal("66.00"),
        fat_grams=Decimal("18.00"),
        ingredients=("Kalkun", "Couscous", "Squash", "Tomatsaus", "Egg"),
        allergen_codes=("egg", "gluten"),
    ),
    MealSeed(
        name="Biff stroganoff med potetmos",
        description="Mør biff med sopp og løk i kremet saus, servert med potetmos.",
        price_nok=Decimal("149.00"),
        calories=690,
        protein_grams=Decimal("45.00"),
        carbohydrate_grams=Decimal("58.00"),
        fat_grams=Decimal("29.00"),
        ingredients=("Storfekjøtt", "Poteter", "Sjampinjong", "Rømme", "Løk", "Sennep"),
        allergen_codes=("milk", "mustard"),
    ),
    MealSeed(
        name="Middelhavspasta med laks",
        description="Fullkornspasta med laks, tomat, spinat og oliven.",
        price_nok=Decimal("145.00"),
        calories=665,
        protein_grams=Decimal("41.00"),
        carbohydrate_grams=Decimal("70.00"),
        fat_grams=Decimal("24.00"),
        ingredients=("Laks", "Fullkornspasta", "Tomat", "Spinat", "Oliven"),
        allergen_codes=("fish", "gluten"),
    ),
    MealSeed(
        name="Linsegryte med søtpotet",
        description="Varmende gryte med røde linser, søtpotet, tomat, spinat og kokosmelk.",
        price_nok=Decimal("115.00"),
        calories=520,
        protein_grams=Decimal("21.00"),
        carbohydrate_grams=Decimal("76.00"),
        fat_grams=Decimal("14.00"),
        ingredients=("Røde linser", "Søtpotet", "Tomat", "Spinat", "Kokosmelk"),
    ),
    MealSeed(
        name="Stekt ris med egg",
        description="Stekt jasminris med egg, erter, gulrot, vårløk og soyasaus.",
        price_nok=Decimal("109.00"),
        calories=545,
        protein_grams=Decimal("23.00"),
        carbohydrate_grams=Decimal("79.00"),
        fat_grams=Decimal("15.00"),
        ingredients=("Jasminris", "Egg", "Erter", "Gulrot", "Vårløk", "Soyasaus"),
        allergen_codes=("egg", "gluten", "soy"),
    ),
)

INGREDIENT_NAMES = tuple(
    dict.fromkeys(ingredient for meal in MEALS for ingredient in meal.ingredients)
)
