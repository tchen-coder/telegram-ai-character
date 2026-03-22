from typing import Optional


DEFAULT_RELATIONSHIP = 1
DEFAULT_INITIAL_RV = 15
DEFAULT_UPDATE_FREQUENCY = 1
DEFAULT_MAX_NEGATIVE_DELTA = 3
DEFAULT_MAX_POSITIVE_DELTA = 15
DEFAULT_RECENT_WINDOW_SIZE = 12
MIN_RV = 0
MAX_RV = 100

RELATIONSHIP_PROMPT_META = {
    1: {"key": "friend", "label": "朋友", "floor_rv": 0, "unlock_threshold": 40},
    2: {"key": "partner", "label": "恋人", "floor_rv": 40, "unlock_threshold": 70},
    3: {"key": "lover", "label": "爱人", "floor_rv": 70, "unlock_threshold": 100},
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
    return str(RELATIONSHIP_PROMPT_META[relationship]["key"])


def relationship_label(value: Optional[int]) -> str:
    relationship = normalize_relationship(value)
    return str(RELATIONSHIP_PROMPT_META[relationship]["label"])


def relationship_floor(value: Optional[int]) -> int:
    relationship = normalize_relationship(value)
    return int(RELATIONSHIP_PROMPT_META[relationship]["floor_rv"])


def relationship_threshold(value: Optional[int]) -> int:
    relationship = normalize_relationship(value)
    return int(RELATIONSHIP_PROMPT_META[relationship]["unlock_threshold"])


def clamp_rv(value: Optional[int], *, lower: int = MIN_RV, upper: int = MAX_RV) -> int:
    try:
        rv = int(value if value is not None else DEFAULT_INITIAL_RV)
    except (TypeError, ValueError):
        rv = DEFAULT_INITIAL_RV
    return max(lower, min(upper, rv))


def relationship_from_rv(value: Optional[int]) -> int:
    rv = clamp_rv(value)
    if rv >= relationship_floor(3):
        return 3
    if rv >= relationship_floor(2):
        return 2
    return 1


def clamp_update_frequency(value: Optional[int]) -> int:
    try:
        frequency = int(value or DEFAULT_UPDATE_FREQUENCY)
    except (TypeError, ValueError):
        frequency = DEFAULT_UPDATE_FREQUENCY
    return max(1, min(10, frequency))


def initial_rv_for_relationship(
    relationship: Optional[int],
    initial_rv: Optional[int] = DEFAULT_INITIAL_RV,
) -> int:
    normalized = normalize_relationship(relationship)
    return max(relationship_floor(normalized), clamp_rv(initial_rv))


def default_stage_names() -> list[str]:
    return [str(RELATIONSHIP_PROMPT_META[item]["label"]) for item in ordered_relationships()]


def default_stage_floors() -> list[int]:
    return [int(RELATIONSHIP_PROMPT_META[item]["floor_rv"]) for item in ordered_relationships()]


def default_stage_thresholds() -> list[int]:
    return [int(RELATIONSHIP_PROMPT_META[item]["unlock_threshold"]) for item in ordered_relationships()]


def normalize_stage_names(value: Optional[list], default: Optional[list[str]] = None) -> list[str]:
    default_names = list(default or default_stage_names())
    if not isinstance(value, list) or len(value) != len(default_names):
        return default_names

    normalized: list[str] = []
    for index, fallback in enumerate(default_names):
        current = str(value[index] or "").strip()
        normalized.append(current or fallback)
    return normalized


def normalize_stage_values(value: Optional[list], default: list[int]) -> list[int]:
    if not isinstance(value, list) or len(value) != len(default):
        return list(default)

    normalized: list[int] = []
    for index, fallback in enumerate(default):
        try:
            normalized.append(int(value[index]))
        except (TypeError, ValueError):
            normalized.append(int(fallback))
    return normalized
