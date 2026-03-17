from typing import Optional


DEFAULT_RELATIONSHIP = 3

RELATIONSHIP_PROMPT_META = {
    1: {"key": "friend", "label": "朋友"},
    2: {"key": "partner", "label": "恋人"},
    3: {"key": "lover", "label": "灵魂伴侣"},
}


def ordered_relationships() -> list[int]:
    return sorted(RELATIONSHIP_PROMPT_META.keys())


def normalize_relationship(value: Optional[int]) -> int:
    try:
        relationship = int(value or DEFAULT_RELATIONSHIP)
    except (TypeError, ValueError):
        relationship = DEFAULT_RELATIONSHIP
    return relationship if relationship in RELATIONSHIP_PROMPT_META else DEFAULT_RELATIONSHIP


def relationship_key(value: Optional[int]) -> str:
    relationship = normalize_relationship(value)
    return RELATIONSHIP_PROMPT_META[relationship]["key"]


def relationship_label(value: Optional[int]) -> str:
    relationship = normalize_relationship(value)
    return RELATIONSHIP_PROMPT_META[relationship]["label"]
