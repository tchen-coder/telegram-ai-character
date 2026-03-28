from typing import Any, Optional

from app.relationship.domain import DEFAULT_RELATIONSHIP, normalize_relationship


def clean_prompt_text(prompt_text: Optional[str]) -> str:
    return str(prompt_text or "").strip()


def _read_attr(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def build_relationship_prompt_lookup(role: Any) -> dict[int, str]:
    prompt_lookup: dict[int, str] = {}

    for item in getattr(role, "relationship_prompts", []) or []:
        relationship = normalize_relationship(_read_attr(item, "relationship"))
        is_active = bool(_read_attr(item, "is_active", True))
        prompt_text = clean_prompt_text(_read_attr(item, "prompt_text"))
        if not is_active or not prompt_text:
            continue
        prompt_lookup[relationship] = prompt_text

    base_prompt = clean_prompt_text(getattr(role, "system_prompt", None))
    if base_prompt and 1 not in prompt_lookup:
        prompt_lookup[1] = base_prompt

    return prompt_lookup


def select_relationship_prompt(role: Any, relationship: Optional[int]) -> str:
    normalized = normalize_relationship(relationship)
    prompt_lookup = build_relationship_prompt_lookup(role)
    return (
        prompt_lookup.get(normalized)
        or prompt_lookup.get(DEFAULT_RELATIONSHIP)
        or clean_prompt_text(getattr(role, "system_prompt", None))
    )
