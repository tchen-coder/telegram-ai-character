from app.models import UserState, EmotionResult, DecisionResult

class DecisionEngine:
    """决策机：根据状态和情绪生成回复策略"""
    
    def decide(self, state: UserState, emotion: EmotionResult) -> DecisionResult:
        """生成本轮策略参数"""
        
        # 基于情绪分数判断用户情绪档位
        # 热烈: 0.6-1, 温和: 0.3-0.6, 冷淡: 0-0.3
        user_warmth = "hot" if emotion.emotion_score > 0.6 else "warm" if emotion.emotion_score > 0.3 else "cold"
        
        # 决策回复情绪
        reply_mood = self._decide_reply_mood(state, user_warmth)
        
        # 决策调情程度
        flirt_level = self._decide_flirt_level(state, user_warmth)
        
        # 决策情绪变化量
        mood_delta = self._decide_mood_delta(user_warmth, emotion.user_emotion)
        
        # 决策切片和延迟
        split_level = 2
        typing_delay_factor = 1.25 if reply_mood == "cold" else 1.0 if reply_mood == "warm" else 0.8
        
        return DecisionResult(
            user_id=state.user_id,
            reply_mood=reply_mood,
            flirt_level=flirt_level,
            split_level=split_level,
            allow_image=False,
            mood_delta=mood_delta,
            typing_delay_factor=typing_delay_factor
        )
    
    def _decide_reply_mood(self, state: UserState, user_warmth: str) -> str:
        """决策回复情绪"""
        if user_warmth == "hot":
            return "excited" if state.relationship_level >= 2 else "warm"
        elif user_warmth == "warm":
            return "warm"
        else:  # cold
            return "warm" if state.relationship_level >= 2 and state.character_mood > 0.5 else "cold"
    
    def _decide_flirt_level(self, state: UserState, user_warmth: str) -> str:
        """决策调情程度"""
        if state.relationship_level == 1:
            return "low" if user_warmth == "hot" else "none"
        elif state.relationship_level == 2:
            return "high" if user_warmth == "hot" else "medium"
        else:  # level 3
            return "high" if user_warmth != "cold" else "medium"
    
    def _decide_mood_delta(self, user_warmth: str, user_emotion: str) -> float:
        """决策情绪变化量"""
        if user_warmth == "hot":
            return 0.15
        elif user_warmth == "warm":
            return 0.05
        else:
            return -0.05 if user_emotion in ["cold", "sad"] else 0.0

decision_engine = DecisionEngine()
