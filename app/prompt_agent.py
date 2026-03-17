from typing import List, Optional

from app.models import UserState, EmotionResult, DecisionResult, RoleInfo
from app.rag.models import RAGContext
from app.services.chat_service import ChatMessage

class PromptAgent:
    """Prompt Agent：组装发给模型的 Prompt 和调度参数"""

    def build_prompt(
        self,
        role_info: RoleInfo,
        state: UserState,
        emotion: EmotionResult,
        decision: DecisionResult,
        conversation_history: Optional[List[ChatMessage]] = None,
        rag_context: Optional[RAGContext] = None,
    ) -> tuple[str, str]:
        """组装完整 Prompt，返回 (system_prompt, user_prompt)"""

        system_prompt = role_info.system_prompt

        relationship_desc = {1: "朋友", 2: "恋人", 3: "灵魂伴侣"}
        mood_desc = {
            "cold": "冷淡、简短、有点疏离",
            "warm": "温和、友好、关心",
            "excited": "热情、活泼、开心"
        }
        flirt_desc = {
            "none": "不调情",
            "low": "轻微暧昧",
            "medium": "适度调情",
            "high": "明显调情撒娇"
        }
        history_text = self._format_history(conversation_history or [])
        rag_text = self._format_rag_context(rag_context)

        user_prompt = f"""## 角色信息
- 角色名称: {role_info.role_name}
- 场景: {role_info.scenario or '日常对话'}

## 当前状态
- 用户名: {state.user_name or '用户'}
- 关系等级: {state.relationship_level} ({relationship_desc.get(state.relationship_level, '朋友')})
- 你的情绪强度: {state.character_mood:.1f} (0=低落, 1=高涨)
- 互动次数: {state.interaction_count}

## 本轮策略
- 回复情绪: {decision.reply_mood} ({mood_desc.get(decision.reply_mood, '温和')})
- 调情程度: {decision.flirt_level} ({flirt_desc.get(decision.flirt_level, '不调情')})

## 最近30条上下文
{history_text}

## RAG检索上下文
{rag_text}

## 用户输入
- 内容: {emotion.user_text}
- 用户情绪: {emotion.user_emotion} (分数: {emotion.emotion_score:.1f})
- 意图: {emotion.intent}

## 输出风格约束
- 回复要像真人聊天，不要一次性写成长段大作文。
- 默认按完整句子表达，通常优先按句号、问号、感叹号形成自然分段。
- 每段通常控制在 40 到 80 字，必要时可以更长，但不要为了控字数删掉关键信息。
- 段与段之间要有推进感，像“先有动作，再说话，再补一句”。
- 允许加入轻微动作描写、神态描写、停顿感，例如：轻笑、靠近、顿了顿、压低声音。
- 优先使用短句、口语句，不要连续堆砌长句。
- 先接住用户刚刚那句话的语气和情绪，再往下推进，不要一上来就只顾角色设定和场景推进。
- 不要每一句都把话题推到最直白或最露骨的位置，要保留一点试探、留白、停顿和真实聊天里的缓冲。
- 允许出现更像真人的自然反应，例如反问、迟疑、顺着对方原话接一句、先安抚再挑逗、先解释再靠近。
- 优先让人感觉是在和一个真实的人聊天，而不是在背设定、念剧情或强行推进主题。
- 回答必须把核心意思说完整，不能因为分段或节奏要求而故意缩写、跳句、漏掉动作或情绪表达。
- 不要写“作为AI”这类出戏表达。
- 不要输出条目、标题、说明书格式。

请根据以上信息，以角色身份回复用户，风格像正在实时聊天的人。"""

        return system_prompt, user_prompt
    
    def get_dispatch_params(self, decision: DecisionResult) -> dict:
        """获取调度参数"""
        return {
            "split_level": decision.split_level,
            "typing_delay_factor": decision.typing_delay_factor,
            "allow_image": decision.allow_image
        }

    @staticmethod
    def _format_history(conversation_history: List[ChatMessage]) -> str:
        if not conversation_history:
            return "- 暂无历史对话"

        lines = []
        for msg in conversation_history[-30:]:
            speaker = "用户" if msg.message_type == "user" else "角色"
            lines.append(f"- {speaker}: {msg.content}")
        return "\n".join(lines)

    @staticmethod
    def _format_rag_context(rag_context: Optional[RAGContext]) -> str:
        if not rag_context or not rag_context.has_content():
            return "- 暂无命中的长期记忆或角色知识"

        lines: list[str] = []
        if rag_context.role_knowledge:
            lines.append("### 角色知识")
            for item in rag_context.role_knowledge:
                source_type = item.metadata.get("source_type", "unknown")
                lines.append(f"- [{source_type}] {item.content}")

        if rag_context.conversation_memory:
            lines.append("### 长期记忆")
            for item in rag_context.conversation_memory:
                message_type = item.metadata.get("message_type", "memory")
                speaker = "用户" if message_type == "user" else "角色"
                lines.append(f"- [{speaker}] {item.content}")

        return "\n".join(lines)

prompt_agent = PromptAgent()
