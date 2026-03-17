import pytest
import asyncio
from unittest.mock import AsyncMock
from datetime import datetime

# 测试理解层
class TestUnderstandingLayer:
    
    def test_happy_emotion(self):
        from app.understanding import understanding_layer
        result = asyncio.run(understanding_layer.analyze("今天好开心啊！"))
        assert result.user_emotion == "happy"
        assert result.emotion_score > 0.5
    
    def test_sad_emotion(self):
        from app.understanding import understanding_layer
        result = asyncio.run(understanding_layer.analyze("我今天有点难过"))
        assert result.user_emotion == "sad"
        assert result.emotion_score < 0.5
    
    def test_neutral_emotion(self):
        from app.understanding import understanding_layer
        result = asyncio.run(understanding_layer.analyze("今天天气不错"))
        assert result.user_emotion == "neutral"
    
    def test_greeting_intent(self):
        from app.understanding import understanding_layer
        result = asyncio.run(understanding_layer.analyze("你好呀"))
        assert result.intent == "greeting"
    
    def test_question_intent(self):
        from app.understanding import understanding_layer
        result = asyncio.run(understanding_layer.analyze("你在干什么？"))
        assert result.intent == "question"


# 测试决策机
class TestDecisionEngine:
    
    def test_hot_user_level1(self):
        from app.decision import decision_engine
        from app.models import UserState, EmotionResult
        
        state = UserState(user_id="test", role_id=1, relationship_level=1, character_mood=0.5)
        emotion = EmotionResult(
            user_text="太开心了",
            user_emotion="happy",
            emotion_score=0.8,
            intent="daily_chat"
        )
        
        result = decision_engine.decide(state, emotion)
        assert result.reply_mood == "warm"
        assert result.flirt_level == "low"
    
    def test_hot_user_level2(self):
        from app.decision import decision_engine
        from app.models import UserState, EmotionResult
        
        state = UserState(user_id="test", role_id=1, relationship_level=2, character_mood=0.5)
        emotion = EmotionResult(
            user_text="太开心了",
            user_emotion="happy",
            emotion_score=0.8,
            intent="daily_chat"
        )
        
        result = decision_engine.decide(state, emotion)
        assert result.reply_mood == "excited"
        assert result.flirt_level == "high"
    
    def test_cold_user_level1(self):
        from app.decision import decision_engine
        from app.models import UserState, EmotionResult
        
        state = UserState(user_id="test", role_id=1, relationship_level=1, character_mood=0.3)
        emotion = EmotionResult(
            user_text="哦",
            user_emotion="cold",
            emotion_score=0.2,
            intent="daily_chat"
        )
        
        result = decision_engine.decide(state, emotion)
        assert result.reply_mood == "cold"
        assert result.flirt_level == "none"


# 测试调度层
class TestDispatchLayer:
    
    def test_split_single(self):
        from app.dispatch import dispatch_layer
        segments = dispatch_layer.split_message("你好", 1)
        assert len(segments) == 1
    
    def test_split_multiple(self):
        from app.dispatch import dispatch_layer
        text = "你好啊。今天天气真不错！我们出去玩吧？"
        segments = dispatch_layer.split_message(text, 3)
        assert segments == ["你好啊。", "今天天气真不错！", "我们出去玩吧？"]

    def test_split_level_one_keeps_whole_message(self):
        from app.dispatch import dispatch_layer
        text = "你好啊。今天天气真不错！我们出去玩吧？"
        segments = dispatch_layer.split_message(text, 1)
        assert segments == [text]

    def test_split_level_two_splits_by_sentence(self):
        from app.dispatch import dispatch_layer
        text = "你好啊。今天天气真不错！我们出去玩吧？"
        segments = dispatch_layer.split_message(text, 2)
        assert segments == ["你好啊。", "今天天气真不错！", "我们出去玩吧？"]
    
    def test_delay_calculation(self):
        from app.dispatch import dispatch_layer
        delay = dispatch_layer.calc_delay("你好", 1.0)
        assert 500 <= delay <= 5000
        
        # 使用较长文本测试延迟系数差异
        long_text = "这是一段比较长的文本用于测试延迟计算"
        delay_fast = dispatch_layer.calc_delay(long_text, 0.5)
        delay_slow = dispatch_layer.calc_delay(long_text, 2.0)
        assert delay_fast < delay_slow

    def test_retry_telegram_call_success_after_timeout(self):
        from telegram.error import TimedOut
        from app.dispatch import DispatchLayer

        dispatch_layer = DispatchLayer()
        operation = AsyncMock(side_effect=[TimedOut("timeout"), "ok"])

        result = asyncio.run(dispatch_layer._retry_telegram_call(operation))

        assert result == "ok"
        assert operation.await_count == 2


class TestChatHistoryHelpers:

    def test_opening_image_moves_to_first_assistant_slot(self):
        from app.services.chat_service import ChatMessage, ChatService

        service = ChatService(None)
        messages = [
            ChatMessage(
                id=1,
                user_id="u1",
                role_id=1,
                message_type="assistant",
                content="开场白文本",
                created_at=datetime.now(),
            ),
            ChatMessage(
                id=2,
                user_id="u1",
                role_id=1,
                message_type="user",
                content="你好",
                created_at=datetime.now(),
            ),
            ChatMessage(
                id=3,
                user_id="u1",
                role_id=1,
                message_type="assistant_image",
                content="",
                meta_json={"source": "role_opening", "image_type": "opening"},
                created_at=datetime.now(),
            ),
        ]

        ordered = service.ensure_opening_image_first(messages)

        assert ordered[0].message_type == "assistant_image"
        assert ordered[1].message_type == "assistant"
        assert ordered[2].message_type == "user"

    def test_extract_latest_role_reply_skips_user_and_image_messages(self):
        from app.api.services import _extract_latest_role_reply
        from app.services.chat_service import ChatMessage

        messages = [
            ChatMessage(
                id=1,
                user_id="u1",
                role_id=1,
                message_type="assistant",
                content="上一条角色回复",
                created_at=datetime.now(),
            ),
            ChatMessage(
                id=2,
                user_id="u1",
                role_id=1,
                message_type="assistant_image",
                content="",
                meta_json={"source": "role_opening"},
                created_at=datetime.now(),
            ),
            ChatMessage(
                id=3,
                user_id="u1",
                role_id=1,
                message_type="user",
                content="我最后发了一句",
                created_at=datetime.now(),
            ),
        ]

        assert _extract_latest_role_reply(messages) == "上一条角色回复"


# 测试 Prompt Agent
class TestPromptAgent:
    
    def test_build_prompt(self):
        from app.prompt_agent import prompt_agent
        from app.models import UserState, EmotionResult, DecisionResult, RoleInfo
        from app.services.chat_service import ChatMessage
        from datetime import datetime
        
        state = UserState(user_id="test", role_id=1, user_name="测试用户", relationship_level=1)
        role = RoleInfo(
            id=1,
            role_name="测试角色",
            system_prompt="你是测试角色"
        )
        emotion = EmotionResult(
            user_text="你好",
            user_emotion="neutral",
            emotion_score=0.5,
            intent="greeting"
        )
        decision = DecisionResult(
            user_id="test",
            reply_mood="warm",
            flirt_level="none",
            split_level=1
        )
        history = [
            ChatMessage(
                id=1,
                user_id="test",
                role_id=1,
                message_type="user",
                content="第一句",
                created_at=datetime.now(),
            ),
            ChatMessage(
                id=2,
                user_id="test",
                role_id=1,
                message_type="assistant",
                content="第二句",
                created_at=datetime.now(),
            ),
        ]
        
        system_prompt, user_prompt = prompt_agent.build_prompt(
            role, state, emotion, decision, history
        )
        assert system_prompt == "你是测试角色"
        assert "测试用户" in user_prompt
        assert "关系等级: 1" in user_prompt
        assert "warm" in user_prompt
        assert "用户: 第一句" in user_prompt
        assert "角色: 第二句" in user_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
