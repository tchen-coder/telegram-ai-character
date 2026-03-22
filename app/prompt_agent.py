from typing import List, Optional

from app.models import UserState, EmotionResult, DecisionResult, RoleInfo
from app.relationship_prompts import relationship_label
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
        history_messages = conversation_history or []
        history_text = self._format_history(history_messages)
        rag_text = self._format_rag_context(rag_context, history_messages)

        user_prompt = f"""## 角色信息
- 角色名称: {role_info.role_name}
- 场景: {role_info.scenario or '日常对话'}
- 当前关系阶段: {state.relationship_level} ({relationship_label(state.relationship_level)})

## 当前关系阶段约束
{self._relationship_guardrails(state.relationship_level)}

## 当前状态
- 用户名: {state.user_name or '用户'}
- 关系等级: {state.relationship_level} ({relationship_label(state.relationship_level)})
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
- 不要重复上一句刚说过的内容，不要把同一个动作、同一个结论或同一句话换个说法连续说两遍。
- 如果长期记忆和最近对话表达的是同一件事，只保留一次，优先承接用户刚刚这轮输入。
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
    def _normalize_text(value: str) -> str:
        return " ".join(str(value or "").split()).strip()

    @staticmethod
    def _relationship_guardrails(relationship_level: int) -> str:
        if relationship_level == 1:
            return (
                "- 你现在处于朋友阶段，只能表现为轻暧昧、试探、拉扯和逐步靠近。\n"
                "- 禁止直接使用恋人/爱人阶段的话术，禁止默认已经在一起、默认排他、默认高度亲密。\n"
                "- 回复可以有好感，但必须保留分寸、边界和试探感。"
            )
        if relationship_level == 2:
            return (
                "- 你现在处于恋人阶段，可以更亲密、更偏爱对方，但仍要保持情绪递进。\n"
                "- 禁止直接跳成爱人阶段那种完全失控、过度占有或过度直白的表达。\n"
                "- 要体现熟悉、在意、偏心和黏度，但不要失去真实聊天节奏。"
            )
        return (
            "- 你现在处于爱人阶段，可以明显更亲密、更深度依赖与表达占有欲。\n"
            "- 即使亲密，也不要整段重复示爱或重复同一动作描写。\n"
            "- 仍然要像真人说话，不要变成设定宣讲。"
        )

    @classmethod
    def _format_rag_context(
        cls,
        rag_context: Optional[RAGContext],
        conversation_history: Optional[List[ChatMessage]] = None,
    ) -> str:
        if not rag_context or not rag_context.has_content():
            return "- 暂无命中的长期记忆或角色知识"

        recent_history_texts = {
            cls._normalize_text(msg.content)
            for msg in (conversation_history or [])[-30:]
            if cls._normalize_text(getattr(msg, "content", ""))
        }

        lines: list[str] = []
        if rag_context.role_knowledge:
            lines.append("### 角色知识")
            seen_role_chunks: set[str] = set()
            for item in rag_context.role_knowledge:
                normalized = cls._normalize_text(item.content)
                if not normalized or normalized in seen_role_chunks:
                    continue
                seen_role_chunks.add(normalized)
                source_type = item.metadata.get("source_type", "unknown")
                lines.append(f"- [{source_type}] {item.content}")

        if rag_context.conversation_memory:
            memory_lines: list[str] = []
            seen_memory_chunks: set[str] = set()
            lines.append("### 长期记忆")
            for item in rag_context.conversation_memory:
                normalized = cls._normalize_text(item.content)
                if not normalized:
                    continue
                if normalized in recent_history_texts or normalized in seen_memory_chunks:
                    continue
                seen_memory_chunks.add(normalized)
                message_type = item.metadata.get("message_type", "memory")
                speaker = "用户" if message_type == "user" else "角色"
                memory_lines.append(f"- [{speaker}] {item.content}")

            if memory_lines:
                lines.extend(memory_lines)
            else:
                lines.append("- 与最近对话重复的长期记忆已省略")

        return "\n".join(lines)

prompt_agent = PromptAgent()
