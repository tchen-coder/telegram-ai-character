from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    RoleRelationshipConfig,
    UserRoleRelationshipEvent,
    UserRoleRelationshipState,
)
from app.database.repositories import (
    RoleRelationshipConfigRepository,
    UserRoleRelationshipEventRepository,
    UserRoleRelationshipStateRepository,
    UserRoleRepository,
)
from app.relationship.domain import (
    DEFAULT_INITIAL_RV,
    DEFAULT_MAX_NEGATIVE_DELTA,
    DEFAULT_MAX_POSITIVE_DELTA,
    DEFAULT_RECENT_WINDOW_SIZE,
    clamp_rv,
    clamp_update_frequency,
    default_stage_floors,
    default_stage_names,
    default_stage_thresholds,
    normalize_relationship,
    normalize_stage_names,
    normalize_stage_values,
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
    """独立管理关系系统的配置、打分、状态推进和提示词解析。"""

    AUTO_RELATIONSHIP_UPDATES_ENABLED = True

    def __init__(self, session: AsyncSession):
        self.session = session
        self.config_repo = RoleRelationshipConfigRepository(session)
        self.state_repo = UserRoleRelationshipStateRepository(session)
        self.event_repo = UserRoleRelationshipEventRepository(session)
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
        config = await self.ensure_role_config(role.id)
        user_role = await self.user_role_repo.ensure_user_role(user_id, role.id)
        state = await self.ensure_state(
            user_id=user_id,
            role_id=role.id,
            legacy_relationship=getattr(user_role, "relationship", None),
            config=config,
        )

        score_result = self._build_score_result(
            user_text=user_text,
            emotion=emotion,
            recent_messages=recent_messages,
            state=state,
            config=config,
        )
        triggered_update = False
        if self.AUTO_RELATIONSHIP_UPDATES_ENABLED and trigger_message_id is not None:
            triggered_update = await self._apply_user_turn(
                state=state,
                config=config,
                trigger_message_id=trigger_message_id,
                score_result=score_result,
            )

        relationship = normalize_relationship(state.current_stage)
        await self._sync_legacy_relationship(user_role=user_role, relationship=relationship)
        await self.session.flush()

        return RelationshipContext(
            relationship=relationship,
            relationship_key=relationship_key(relationship),
            relationship_label=relationship_label(relationship),
            prompt_text=select_relationship_prompt(role, relationship),
            current_rv=clamp_rv(state.current_rv),
            current_stage=normalize_relationship(state.current_stage),
            max_unlocked_stage=normalize_relationship(state.max_unlocked_stage),
            turn_count=int(state.turn_count or 0),
            update_frequency=clamp_update_frequency(
                state.update_frequency or config.update_frequency
            ),
            last_delta=int(state.last_delta or 0),
            pending_delta=int(state.pending_delta_accumulator or 0),
            triggered_update=triggered_update,
        )

    async def ensure_role_config(self, role_id: int) -> RoleRelationshipConfig:
        config = await self.config_repo.get_by_role_id(role_id)
        if not config:
            config = RoleRelationshipConfig(
                role_id=role_id,
                initial_rv=DEFAULT_INITIAL_RV,
                update_frequency=1,
                max_negative_delta=DEFAULT_MAX_NEGATIVE_DELTA,
                max_positive_delta=DEFAULT_MAX_POSITIVE_DELTA,
                recent_window_size=DEFAULT_RECENT_WINDOW_SIZE,
                stage_names=default_stage_names(),
                stage_floor_rv=default_stage_floors(),
                stage_thresholds=default_stage_thresholds(),
                paid_boost_enabled=False,
                meta_json={},
            )
            await self.config_repo.create(config)
            return config

        changed = False
        normalized_initial_rv = clamp_rv(config.initial_rv)
        if config.initial_rv != normalized_initial_rv:
            config.initial_rv = normalized_initial_rv
            changed = True

        normalized_frequency = max(3, clamp_update_frequency(config.update_frequency))
        if config.update_frequency != normalized_frequency:
            config.update_frequency = normalized_frequency
            changed = True

        normalized_negative = max(1, abs(int(config.max_negative_delta or DEFAULT_MAX_NEGATIVE_DELTA)))
        if int(config.max_negative_delta or 0) != normalized_negative:
            config.max_negative_delta = normalized_negative
            changed = True

        normalized_positive = min(
            8,
            max(1, int(config.max_positive_delta or DEFAULT_MAX_POSITIVE_DELTA)),
        )
        if int(config.max_positive_delta or 0) != normalized_positive:
            config.max_positive_delta = normalized_positive
            changed = True

        normalized_window = max(4, int(config.recent_window_size or DEFAULT_RECENT_WINDOW_SIZE))
        if int(config.recent_window_size or 0) != normalized_window:
            config.recent_window_size = normalized_window
            changed = True

        normalized_names = normalize_stage_names(config.stage_names)
        if config.stage_names != normalized_names:
            config.stage_names = normalized_names
            changed = True

        normalized_floors = normalize_stage_values(config.stage_floor_rv, default_stage_floors())
        normalized_floors[0] = max(0, normalized_floors[0])
        normalized_floors[1] = max(normalized_floors[0], normalized_floors[1])
        normalized_floors[2] = max(normalized_floors[1], normalized_floors[2])
        if config.stage_floor_rv != normalized_floors:
            config.stage_floor_rv = normalized_floors
            changed = True

        normalized_thresholds = normalize_stage_values(
            config.stage_thresholds,
            default_stage_thresholds(),
        )
        normalized_thresholds[0] = max(normalized_floors[1], normalized_thresholds[0])
        normalized_thresholds[1] = max(normalized_thresholds[0], normalized_floors[2], normalized_thresholds[1])
        normalized_thresholds[2] = max(normalized_thresholds[1], normalized_thresholds[2], 100)
        if config.stage_thresholds != normalized_thresholds:
            config.stage_thresholds = normalized_thresholds
            changed = True

        if config.meta_json is None:
            config.meta_json = {}
            changed = True

        if changed:
            await self.config_repo.update(config)
        return config

    async def ensure_state(
        self,
        *,
        user_id: str,
        role_id: int,
        legacy_relationship: Optional[int],
        config: RoleRelationshipConfig,
    ) -> UserRoleRelationshipState:
        state = await self.state_repo.get_by_user_and_role(user_id, role_id)
        seed_relationship = normalize_relationship(legacy_relationship)
        if not state:
            seed_rv = max(self._stage_floor(config, seed_relationship), clamp_rv(config.initial_rv))
            state = UserRoleRelationshipState(
                user_id=user_id,
                role_id=role_id,
                current_rv=seed_rv,
                current_stage=seed_relationship,
                max_unlocked_stage=seed_relationship,
                last_rv=seed_rv,
                last_delta=0,
                last_update_at_turn=0,
                turn_count=0,
                update_frequency=clamp_update_frequency(config.update_frequency),
                pending_delta_accumulator=0,
                paid_boost_rv=0,
                paid_boost_applied=False,
                paid_boost_source=None,
                emotion_summary_text=None,
                emotion_summary_updated_turn=0,
                emotion_adjustment_factor=0.0,
            )
            await self.state_repo.create(state)
            return state

        changed = False
        current_stage = max(
            normalize_relationship(state.current_stage or seed_relationship),
            seed_relationship,
        )
        max_unlocked_stage = max(
            current_stage,
            normalize_relationship(state.max_unlocked_stage or current_stage),
            seed_relationship,
        )
        current_rv = max(
            self._stage_floor(config, current_stage),
            clamp_rv(state.current_rv if state.current_rv is not None else config.initial_rv),
        )
        last_rv = clamp_rv(state.last_rv if state.last_rv is not None else current_rv)
        update_frequency = clamp_update_frequency(state.update_frequency or config.update_frequency)

        if state.current_stage != current_stage:
            state.current_stage = current_stage
            changed = True
        if state.max_unlocked_stage != max_unlocked_stage:
            state.max_unlocked_stage = max_unlocked_stage
            changed = True
        if state.current_rv != current_rv:
            state.current_rv = current_rv
            changed = True
        if state.last_rv != last_rv:
            state.last_rv = last_rv
            changed = True
        if state.update_frequency != update_frequency:
            state.update_frequency = update_frequency
            changed = True
        if state.pending_delta_accumulator is None:
            state.pending_delta_accumulator = 0
            changed = True
        if state.paid_boost_rv is None:
            state.paid_boost_rv = 0
            changed = True
        if state.emotion_summary_updated_turn is None:
            state.emotion_summary_updated_turn = 0
            changed = True
        if state.emotion_adjustment_factor is None:
            state.emotion_adjustment_factor = 0.0
            changed = True

        if changed:
            await self.state_repo.update(state)
        return state

    def _build_score_result(
        self,
        *,
        user_text: str,
        emotion: Optional["EmotionResult"],
        recent_messages: Optional[list[Any]],
        state: UserRoleRelationshipState,
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
        windowed_messages = list(recent_messages or [])[-history_window:]
        return relationship_scorer.score(
            user_text=user_text,
            emotion=emotion,
            recent_messages=windowed_messages,
            current_stage=normalize_relationship(state.current_stage),
            current_rv=clamp_rv(state.current_rv),
            max_negative_delta=int(config.max_negative_delta or DEFAULT_MAX_NEGATIVE_DELTA),
            max_positive_delta=int(config.max_positive_delta or DEFAULT_MAX_POSITIVE_DELTA),
        )

    async def _apply_user_turn(
        self,
        *,
        state: UserRoleRelationshipState,
        config: RoleRelationshipConfig,
        trigger_message_id: int,
        score_result: RelationshipScoreResult,
    ) -> bool:
        rv_before = clamp_rv(state.current_rv)
        stage_before = normalize_relationship(state.current_stage)
        pending_before = int(state.pending_delta_accumulator or 0)

        state.turn_count = int(state.turn_count or 0) + 1
        state.update_frequency = clamp_update_frequency(
            state.update_frequency or config.update_frequency
        )
        triggered_update = state.turn_count == 1 or state.turn_count % state.update_frequency == 0

        event_payload = dict(score_result.payload or {})
        event_payload["update_frequency"] = state.update_frequency

        if triggered_update:
            applied_delta = self._apply_delta_with_floor(
                pending_before + int(score_result.applied_delta or 0),
                config=config,
            )
            stage_after = self._resolve_stage_after_update(
                rv_before=rv_before,
                applied_delta=applied_delta,
                stage_before=stage_before,
                config=config,
            )
            rv_after = max(
                self._stage_floor(config, stage_after),
                clamp_rv(rv_before + applied_delta),
            )

            state.last_rv = rv_before
            state.last_delta = applied_delta
            state.last_update_at_turn = state.turn_count
            state.current_rv = rv_after
            state.current_stage = stage_after
            state.max_unlocked_stage = max(stage_before, stage_after)
            state.pending_delta_accumulator = 0

            event_payload["pending_after"] = 0
            await self.event_repo.create(
                UserRoleRelationshipEvent(
                    user_id=state.user_id,
                    role_id=state.role_id,
                    trigger_message_id=trigger_message_id,
                    turn_index=state.turn_count,
                    triggered_update=True,
                    delta=int(score_result.applied_delta or 0),
                    pending_before=pending_before,
                    applied_delta=applied_delta,
                    rv_before=rv_before,
                    rv_after=rv_after,
                    stage_before=stage_before,
                    stage_after=stage_after,
                    scoring_source="heuristic_v1",
                    reason_text="; ".join(score_result.reasons or ["关系更新"]),
                    payload_json=event_payload,
                )
            )
        else:
            state.pending_delta_accumulator = pending_before + int(score_result.applied_delta or 0)
            event_payload["pending_after"] = state.pending_delta_accumulator
            await self.event_repo.create(
                UserRoleRelationshipEvent(
                    user_id=state.user_id,
                    role_id=state.role_id,
                    trigger_message_id=trigger_message_id,
                    turn_index=state.turn_count,
                    triggered_update=False,
                    delta=int(score_result.applied_delta or 0),
                    pending_before=pending_before,
                    applied_delta=0,
                    rv_before=rv_before,
                    rv_after=rv_before,
                    stage_before=stage_before,
                    stage_after=stage_before,
                    scoring_source="heuristic_v1",
                    reason_text="; ".join(score_result.reasons or ["累计待更新"]),
                    payload_json=event_payload,
                )
            )

        await self.state_repo.update(state)
        return triggered_update

    def _apply_delta_with_floor(self, delta: int, *, config: RoleRelationshipConfig) -> int:
        negative_cap = max(1, abs(int(config.max_negative_delta or DEFAULT_MAX_NEGATIVE_DELTA)))
        if delta < 0:
            return max(-negative_cap, delta)
        return delta

    def _resolve_stage_after_update(
        self,
        *,
        rv_before: int,
        applied_delta: int,
        stage_before: int,
        config: RoleRelationshipConfig,
    ) -> int:
        tentative_rv = clamp_rv(rv_before + applied_delta)
        stage_after = stage_before
        thresholds = self._stage_thresholds(config)
        if tentative_rv >= thresholds[0]:
            stage_after = max(stage_after, 2)
        if tentative_rv >= thresholds[1]:
            stage_after = max(stage_after, 3)
        return normalize_relationship(stage_after)

    def _stage_floor(self, config: RoleRelationshipConfig, relationship: int) -> int:
        floors = self._stage_floors(config)
        index = max(0, min(len(floors) - 1, normalize_relationship(relationship) - 1))
        return int(floors[index])

    def _stage_floors(self, config: RoleRelationshipConfig) -> list[int]:
        return normalize_stage_values(config.stage_floor_rv, default_stage_floors())

    def _stage_thresholds(self, config: RoleRelationshipConfig) -> list[int]:
        return normalize_stage_values(config.stage_thresholds, default_stage_thresholds())

    async def _sync_legacy_relationship(self, *, user_role, relationship: int) -> None:
        normalized = normalize_relationship(relationship)
        if normalize_relationship(getattr(user_role, "relationship", None)) == normalized:
            return
        user_role.relationship = normalized
        user_role.last_interaction_at = datetime.utcnow()
        await self.user_role_repo.update(user_role)
