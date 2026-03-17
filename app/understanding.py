from app.models import EmotionResult

class UnderstandingLayer:
    """理解层：对用户输入做情绪识别和意图分类"""
    
    # 情绪关键词映射
    EMOTION_KEYWORDS = {
        "happy": ["开心", "高兴", "快乐", "哈哈", "太好了", "棒", "喜欢", "爱"],
        "sad": ["难过", "伤心", "哭", "不开心", "郁闷", "烦", "累", "失望"],
        "excited": ["激动", "兴奋", "太棒了", "wow", "天哪", "不敢相信"],
        "cold": ["无聊", "算了", "随便", "哦", "嗯", "好吧"],
    }
    
    # 意图关键词
    INTENT_KEYWORDS = {
        "greeting": ["你好", "hi", "hello", "早", "晚安", "在吗"],
        "question": ["吗", "?", "？", "什么", "怎么", "为什么", "哪"],
    }
    
    async def analyze(self, user_text: str) -> EmotionResult:
        """分析用户输入，返回情绪和意图"""
        text_lower = user_text.lower()
        
        # 情绪识别
        emotion = "neutral"
        emotion_score = 0.5
        keywords = []
        
        for emo, words in self.EMOTION_KEYWORDS.items():
            for word in words:
                if word in text_lower:
                    emotion = emo
                    keywords.append(word)
                    emotion_score = 0.7 if emo in ["happy", "excited"] else 0.3
                    break
            if emotion != "neutral":
                break
        
        # 意图识别
        intent = "daily_chat"
        for int_type, words in self.INTENT_KEYWORDS.items():
            for word in words:
                if word in text_lower:
                    intent = int_type
                    break
        
        return EmotionResult(
            user_text=user_text,
            user_emotion=emotion,
            emotion_score=emotion_score,
            intent=intent,
            keywords=keywords
        )

understanding_layer = UnderstandingLayer()
