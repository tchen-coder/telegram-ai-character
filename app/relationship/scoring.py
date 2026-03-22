from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from app.relationship.domain import (
    DEFAULT_MAX_NEGATIVE_DELTA,
    DEFAULT_MAX_POSITIVE_DELTA,
    clamp_rv,
    relationship_label,
)

if TYPE_CHECKING:
    from app.models import EmotionResult


def _message_type(message: Any) -> str:
    raw_value = getattr(message, "message_type", "")
    return raw_value.value if hasattr(raw_value, "value") else str(raw_value)


def _message_content(message: Any) -> str:
    return str(getattr(message, "content", "") or "").strip()


@dataclass(frozen=True)
class RelationshipScoreResult:
    raw_delta: int
    applied_delta: int
    reasons: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)


class HeuristicRelationshipScorer:
    """关系值打分器。当前先用稳定的规则评分，后续可替换成 LLM scorer。"""

    STRONG_POSITIVE_KEYWORDS = {
        "love": ["爱你", "爱死你", "喜欢你", "想你", "离不开你"],
        "commitment": ["想和你在一起", "想一直陪你", "只想要你", "你是我的"],
    }
    FLIRT_KEYWORDS = {
        "affection": ["抱抱", "亲亲", "贴贴", "想抱", "想亲", "想贴着你"],
        "addressing": ["宝贝", "亲爱的", "老婆", "老公", "主人"],
        "praise": ["你好可爱", "你好甜", "你好香", "你好漂亮", "你好性感"],
    }
    EROTIC_KEYWORDS = {
        "intimacy": [
            "接吻", "舌吻", "摸你", "摸胸", "摸腿", "脱衣服", "做爱", "上床",
            "内射", "高潮", "想狠狠干", "想进入你", "舔", "口交",
        ],
    }
    CARE_KEYWORDS = {
        "care": ["想你了", "在吗", "早点睡", "辛苦了", "别累着", "注意休息", "陪陪我"],
    }
    NEGATIVE_KEYWORDS = {
        "hard_reject": ["滚", "闭嘴", "别碰我", "离我远点", "讨厌你", "恶心", "烦死了"],
        "soft_reject": ["别这样", "不要", "停", "算了", "没兴趣", "不想聊", "先这样"],
        "cold": ["哦", "嗯", "随便", "无聊", "呵呵"],
    }

    def score(
        self,
        *,
        user_text: str,
        emotion: "EmotionResult",
        recent_messages: Optional[list[Any]],
        current_stage: int,
        current_rv: int,
        max_negative_delta: int = DEFAULT_MAX_NEGATIVE_DELTA,
        max_positive_delta: int = DEFAULT_MAX_POSITIVE_DELTA,
    ) -> RelationshipScoreResult:
        text = str(user_text or "").strip()
        lowered = text.lower()
        reasons: list[str] = []
        payload: dict = {
            "stage_before": current_stage,
            "stage_label_before": relationship_label(current_stage),
            "rv_before": clamp_rv(current_rv),
            "emotion": emotion.user_emotion,
            "intent": emotion.intent,
            "keywords": list(emotion.keywords or []),
        }

        score = 0
        negative_hit = False

        if text:
            score += 1
            reasons.append("有效输入")

        keyword_delta, keyword_reasons, keyword_payload = self._score_keywords(text, lowered)
        score += keyword_delta
        reasons.extend(keyword_reasons)
        payload.update(keyword_payload)
        negative_hit = keyword_payload.get("negative_hit", False)

        emotion_delta, emotion_reasons = self._score_emotion(emotion, negative_hit=negative_hit)
        score += emotion_delta
        reasons.extend(emotion_reasons)

        continuity_delta, continuity_reasons, continuity_payload = self._score_recent_history(
            recent_messages or [],
            negative_hit=negative_hit,
            positive_now=score > 0,
        )
        score += continuity_delta
        reasons.extend(continuity_reasons)
        payload.update(continuity_payload)

        if len(text) >= 24 and score > 0:
            score += 1
            reasons.append("输入较完整")

        if emotion.intent == "greeting" and score >= 0:
            score += 1
            reasons.append("主动打招呼")
        elif emotion.intent == "question" and not negative_hit:
            score += 1
            reasons.append("主动推进对话")

        capped = max(-abs(int(max_negative_delta)), min(int(max_positive_delta), score))
        payload["raw_delta"] = int(score)
        payload["applied_delta"] = int(capped)

        return RelationshipScoreResult(
            raw_delta=int(score),
            applied_delta=int(capped),
            reasons=reasons or ["常规互动"],
            payload=payload,
        )

    def _score_keywords(self, original_text: str, lowered_text: str) -> tuple[int, list[str], dict]:
        score = 0
        reasons: list[str] = []
        payload: dict = {"matched_groups": [], "negative_hit": False}

        def contains_any(words: list[str]) -> bool:
            return any(word.lower() in lowered_text for word in words)

        for group, words in self.STRONG_POSITIVE_KEYWORDS.items():
            if contains_any(words):
                score += 4
                reasons.append(f"强情感表达:{group}")
                payload["matched_groups"].append(group)

        for group, words in self.FLIRT_KEYWORDS.items():
            if contains_any(words):
                score += 2
                reasons.append(f"暧昧信号:{group}")
                payload["matched_groups"].append(group)

        for group, words in self.EROTIC_KEYWORDS.items():
            if contains_any(words):
                score += 5
                reasons.append(f"亲密推进:{group}")
                payload["matched_groups"].append(group)

        for group, words in self.CARE_KEYWORDS.items():
            if contains_any(words):
                score += 2
                reasons.append(f"依赖/关心:{group}")
                payload["matched_groups"].append(group)

        for group, words in self.NEGATIVE_KEYWORDS.items():
            if contains_any(words):
                penalty = -3 if group == "hard_reject" else -2 if group == "soft_reject" else -1
                score += penalty
                reasons.append(f"负反馈:{group}")
                payload["matched_groups"].append(group)
                payload["negative_hit"] = True

        if "?" in original_text or "？" in original_text:
            score += 1
            reasons.append("主动提问")

        return score, reasons, payload

    @staticmethod
    def _score_emotion(
        emotion: "EmotionResult",
        *,
        negative_hit: bool,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []

        if emotion.user_emotion == "happy":
            score += 1
            reasons.append("情绪积极")
        elif emotion.user_emotion == "excited":
            score += 2
            reasons.append("情绪高涨")
        elif emotion.user_emotion == "cold":
            score -= 1
            reasons.append("情绪偏冷")
        elif emotion.user_emotion == "sad" and negative_hit:
            score -= 1
            reasons.append("消极并伴随负反馈")

        return score, reasons

    def _score_recent_history(
        self,
        recent_messages: list[Any],
        *,
        negative_hit: bool,
        positive_now: bool,
    ) -> tuple[int, list[str], dict]:
        user_messages = [
            _message_content(message)
            for message in recent_messages
            if _message_type(message) == "user" and _message_content(message)
        ]
        recent_user_messages = user_messages[-4:]
        positive_history = 0
        cold_history = 0

        for text in recent_user_messages[:-1]:
            lowered = text.lower()
            if any(
                word.lower() in lowered
                for words in list(self.STRONG_POSITIVE_KEYWORDS.values()) + list(self.FLIRT_KEYWORDS.values())
                for word in words
            ):
                positive_history += 1
            if any(word.lower() in lowered for word in self.NEGATIVE_KEYWORDS["cold"]):
                cold_history += 1

        score = 0
        reasons: list[str] = []
        payload = {
            "recent_user_turns": len(recent_user_messages),
            "recent_positive_turns": positive_history,
            "recent_cold_turns": cold_history,
        }

        if positive_now and positive_history >= 2:
            score += 1
            reasons.append("近期互动连续升温")
        if negative_hit and cold_history >= 1:
            score -= 1
            reasons.append("近期互动连续降温")

        return score, reasons, payload


relationship_scorer = HeuristicRelationshipScorer()
