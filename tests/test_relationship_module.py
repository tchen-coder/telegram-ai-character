from types import SimpleNamespace

from app.relationship.domain import (
    DEFAULT_RELATIONSHIP,
    initial_rv_for_relationship,
    relationship_label,
)
from app.relationship.prompting import select_relationship_prompt
from app.relationship.scoring import relationship_scorer
from app.relationship.service import RelationshipService
from app.models import EmotionResult


def test_default_relationship_is_friend_stage():
    assert DEFAULT_RELATIONSHIP == 1


def test_stage_three_label_is_ai_ren():
    assert relationship_label(3) == "爱人"


def test_initial_rv_respects_existing_stage_floor():
    assert initial_rv_for_relationship(1, 15) == 15
    assert initial_rv_for_relationship(2, 15) == 40
    assert initial_rv_for_relationship(3, 15) == 70


def test_select_relationship_prompt_prefers_stage_specific_prompt():
    role = SimpleNamespace(
        system_prompt="base-prompt",
        system_prompt_friend="friend-legacy",
        system_prompt_partner="partner-legacy",
        system_prompt_lover="lover-legacy",
        relationship_prompts=[
            SimpleNamespace(relationship=1, prompt_text="friend-structured", is_active=True),
            SimpleNamespace(relationship=2, prompt_text="partner-structured", is_active=True),
        ],
    )

    assert select_relationship_prompt(role, 2) == "partner-structured"


def test_select_relationship_prompt_falls_back_to_friend_prompt():
    role = SimpleNamespace(
        system_prompt="base-prompt",
        system_prompt_friend="friend-legacy",
        system_prompt_partner="",
        system_prompt_lover="",
        relationship_prompts=[
            {"relationship": 1, "prompt_text": "friend-structured", "is_active": True},
        ],
    )

    assert select_relationship_prompt(role, 3) == "friend-structured"


def test_relationship_scorer_caps_negative_delta():
    emotion = EmotionResult(
        user_text="滚，别碰我",
        user_emotion="cold",
        emotion_score=0.1,
        intent="daily_chat",
        keywords=[],
    )

    result = relationship_scorer.score(
        user_text=emotion.user_text,
        emotion=emotion,
        recent_messages=[],
        current_stage=1,
        current_rv=15,
    )

    assert result.applied_delta == -3


def test_relationship_scorer_rewards_flirt_message():
    emotion = EmotionResult(
        user_text="宝贝，我好想你，今晚想抱着你睡",
        user_emotion="happy",
        emotion_score=0.8,
        intent="daily_chat",
        keywords=["想"],
    )

    result = relationship_scorer.score(
        user_text=emotion.user_text,
        emotion=emotion,
        recent_messages=[],
        current_stage=1,
        current_rv=15,
    )

    assert result.applied_delta >= 6


def test_relationship_service_upgrades_stage_with_thresholds():
    service = RelationshipService(None)
    config = SimpleNamespace(
        max_negative_delta=3,
        stage_floor_rv=[0, 40, 70],
        stage_thresholds=[40, 70, 100],
    )

    assert service._resolve_stage_after_update(  # noqa: SLF001
        rv_before=38,
        applied_delta=4,
        stage_before=1,
        config=config,
    ) == 2
    assert service._resolve_stage_after_update(  # noqa: SLF001
        rv_before=68,
        applied_delta=5,
        stage_before=2,
        config=config,
    ) == 3
