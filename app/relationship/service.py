from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import RoleRelationshipConfig
from app.database.repositories import (
    RoleRelationshipConfigRepository,
    UserRoleRepository,
)
from app.relationship.domain import (
    DEFAULT_INITIAL_RV,
    DEFAULT_MAX_NEGATIVE_DELTA,
    DEFAULT_MAX_POSITIVE_DELTA,
    DEFAULT_RECENT_WINDOW_SIZE,
    DEFAULT_RELATIONSHIP,
    DEFAULT_UPDATE_FREQUENCY,
    clamp_rv,
    normalize_relationship,
    normalize_stage_names,
    normalize_stage_values,
    relationship_floor,
    relationship_key,
    relationship_label,
)
from app.relationship.prompting import select_relationship_prompt
from app.relationship.scoring import RelationshipScoreResult, relationship_scorer

if TYPE_CHECKING:
    from app.models import EmotionResult


@dataclass(frozen=True)
class RelationshipContext:
    relationship: int
    relationship_key: str
    relationship_label: str
    prompt_text: str
    current_rv: int
    current_stage: int
    max_unlocked_stage: int
    turn_count: int
    update_frequency: int
    last_delta: int
    pending_delta: int
    triggered_update: bool


class RelationshipService:
    """关系系统仅保留 user_roles.relationship 作为状态来源。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.config_repo = RoleRelationshipConfigRepository(session)
        self.user_role_repo = UserRoleRepository(session)

    async def resolve_generation_context(
        self,
        *,
        role,
        user_id: str,
        user_text: str = "",
        emotion: Optional["EmotionResult"] = None,
        recent_messages: Optional[list[Any]] = None,
        trigger_message_id: Optional[int] = None,
    ) -> RelationshipContext:
        del trigger_message_id

        config = await self.ensure_role_config(role.id)
        user_role = await self.user_role_repo.ensure_user_role(user_id, role.id)
        current_relationship = normalize_relationship(getattr(user_role, "relationship", None))
        score_result = self._build_score_result(
            user_text=user_text,
            emotion=emotion,
            recent_messages=recent_messages,
            relationship=current_relationship,
            config=config,
        )

        next_relationship = self._resolve_next_relationship(
            current_relationship=current_relationship,
            score_result=score_result,
            config=config,
        )
        triggered_update = next_relationship != current_relationship
        if triggered_update:
            await self.user_role_repo.update_relationship(
                user_id=user_id,
                role_id=role.id,
                relationship=next_relationship,
            )
            current_relationship = next_relationship

        current_rv = relationship_floor(current_relationship)
        return RelationshipContext(
            relationship=current_relationship,
            relationship_key=relationship_key(current_relationship),
            relationship_label=self._stage_label(config, current_relationship),
            prompt_text=select_relationship_prompt(role, current_relationship),
            current_rv=clamp_rv(current_rv),
            current_stage=current_relationship,
            max_unlocked_stage=current_relationship,
            turn_count=0,
            update_frequency=int(config.update_frequency or DEFAULT_UPDATE_FREQUENCY),
            last_delta=int(score_result.applied_delta or 0),
            pending_delta=0,
            triggered_update=triggered_update,
        )

    async def ensure_role_config(self, role_id: int) -> RoleRelationshipConfig:
        config = await self.config_repo.get_by_role_id(role_id)
        if not config:
            config = RoleRelationshipConfig(
                role_id=role_id,
                initial_rv=DEFAULT_INITIAL_RV,
                update_frequency=DEFAULT_UPDATE_FREQUENCY,
                max_negative_delta=DEFAULT_MAX_NEGATIVE_DELTA,
                max_positive_delta=DEFAULT_MAX_POSITIVE_DELTA,
                recent_window_size=DEFAULT_RECENT_WINDOW_SIZE,
                stage_names=["朋友", "恋人", "爱人"],
                stage_floor_rv=[0, 40, 70],
                stage_thresholds=[40, 70, 100],
                paid_boost_enabled=False,
                meta_json={},
            )
            await self.config_repo.create(config)
            return config

        changed = False
        if config.meta_json is None:
            config.meta_json = {}
            changed = True
        normalized_names = normalize_stage_names(config.stage_names, ["朋友", "恋人", "爱人"])
        if config.stage_names != normalized_names:
            config.stage_names = normalized_names
            changed = True
        normalized_floors = normalize_stage_values(config.stage_floor_rv, [0, 40, 70])
        if config.stage_floor_rv != normalized_floors:
            config.stage_floor_rv = normalized_floors
            changed = True
        normalized_thresholds = normalize_stage_values(config.stage_thresholds, [40, 70, 100])
        if config.stage_thresholds != normalized_thresholds:
            config.stage_thresholds = normalized_thresholds
            changed = True
        if changed:
            await self.config_repo.update(config)
        return config

    def _build_score_result(
        self,
        *,
        user_text: str,
        emotion: Optional["EmotionResult"],
        recent_messages: Optional[list[Any]],
        relationship: int,
        config: RoleRelationshipConfig,
    ) -> RelationshipScoreResult:
        if not emotion:
            return RelationshipScoreResult(
                raw_delta=0,
                applied_delta=0,
                reasons=["未提供情绪输入"],
                payload={},
            )

        history_window = int(config.recent_window_size or DEFAULT_RECENT_WINDOW_SIZE)
        return relationship_scorer.score(
            user_text=user_text,
            emotion=emotion,
            recent_messages=list(recent_messages or [])[-history_window:],
            current_stage=relationship,
            current_rv=relationship_floor(relationship),
            max_negative_delta=int(config.max_negative_delta or DEFAULT_MAX_NEGATIVE_DELTA),
            max_positive_delta=int(config.max_positive_delta or DEFAULT_MAX_POSITIVE_DELTA),
        )

    def _resolve_next_relationship(
        self,
        *,
        current_relationship: int,
        score_result: RelationshipScoreResult,
        config: RoleRelationshipConfig,
    ) -> int:
        relationship = normalize_relationship(current_relationship)
        delta = int(score_result.applied_delta or 0)

        if relationship >= 3 or delta <= 0:
            return relationship

        thresholds = normalize_stage_values(config.stage_thresholds, [40, 70, 100])
        promote_score = self._promotion_score(delta, config)

        if relationship == 1 and promote_score >= thresholds[0]:
            return 2
        if relationship == 2 and promote_score >= thresholds[1]:
            return 3
        return relationship

    @staticmethod
    def _promotion_score(delta: int, config: RoleRelationshipConfig) -> int:
        max_positive = max(1, int(config.max_positive_delta or DEFAULT_MAX_POSITIVE_DELTA))
        normalized_delta = max(0, min(max_positive, int(delta or 0)))
        return int(normalized_delta / max_positive * 100)

    @staticmethod
    def _stage_label(config: RoleRelationshipConfig, relationship: int) -> str:
        stage_names = normalize_stage_names(config.stage_names, ["朋友", "恋人", "爱人"])
        index = max(0, min(len(stage_names) - 1, normalize_relationship(relationship) - 1))
        return stage_names[index] or relationship_label(relationship)
