from typing import Literal

Language = Literal["no", "en"]


def localized(original: str, english: str | None, lang: Language) -> str:
    """Preserve custom content when an authored translation has not been supplied."""
    return english if lang == "en" and english else original
